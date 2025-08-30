import os
import json
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

# --- Cấu hình FastAPI ---
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # hoặc ["http://localhost:3000"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Google Sheets ---
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SPREADSHEET_ID = "1D-LIdRIvcGN2R4sti-fCSp7tKcSBkXCTQnvmnXOWaCk"

# Lấy credentials từ biến môi trường trên Render
# Tạo biến môi trường GOOGLE_CREDENTIALS = nội dung JSON service account
try:
    creds_info = json.loads(os.environ["GOOGLE_CREDENTIALS"])
except KeyError:
    raise RuntimeError("Vui lòng cấu hình biến môi trường GOOGLE_CREDENTIALS trên Render")

creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
client = gspread.authorize(creds)
sheet = client.open_by_key(SPREADSHEET_ID).sheet1

# --- API ---
@app.get("/find-data")
def data_found(key: str):
    try:
        extracted_key = key.removeprefix("SG")
        ticket_no = int(key[-1])  # số thứ tự vé (1-5)

        # Map số vé sang cột
        col_map = {1: 21, 2: 22, 3: 23, 4: 24, 5: 25}
        col_index = col_map.get(ticket_no)
        if not col_index:
            return {"found": False, "message": "Chỉ hỗ trợ vé số 1-5"}

        extracted_key = extracted_key[:-1]  # bỏ ký tự cuối
        cell = sheet.find(extracted_key)
        row_number = cell.row
        row = sheet.row_values(row_number)

        checkin_value = sheet.cell(row_number, col_index).value
        if not checkin_value or checkin_value.lower() == "available":
            status = "available"
            checkin_time = None
        elif checkin_value.lower().startswith("checked in"):
            status = "checked_in"
            checkin_time = checkin_value
        else:
            status = "unavailable"
            checkin_time = None

        return {
            "found": True,
            "order_code": key,
            "status": status,
            "checkin_time": checkin_time,
            "row_number": row_number,
            "ticket_no": ticket_no,
            "values": row
        }
    except Exception as e:
        return {"found": False, "message": f"Không tìm thấy '{key}' trong sheet. Lỗi: {e}"}

@app.get("/checkin/{order_code}")
def checkin(order_code: str):
    try:
        if not order_code.startswith("SG") or len(order_code) < 2:
            raise HTTPException(status_code=400, detail="Mã vé không hợp lệ")

        extracted_key = order_code.removeprefix("SG")
        ticket_no_char = extracted_key[-1]
        if not ticket_no_char.isdigit():
            raise HTTPException(status_code=400, detail="Mã vé phải kết thúc bằng số thứ tự vé 1-5")

        ticket_no = int(ticket_no_char)
        if ticket_no not in range(1, 6):
            raise HTTPException(status_code=400, detail="Chỉ hỗ trợ checkin vé số 1-5")

        extracted_key = extracted_key[:-1]  # bỏ ký tự cuối
        cell = sheet.find(extracted_key)
        row_number = cell.row
        col_map = {1: 21, 2: 22, 3: 23, 4: 24, 5: 25}
        col_index = col_map[ticket_no]

        checkin_time = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        cell_value = sheet.cell(row_number, col_index).value

        if not cell_value or cell_value.lower() == "available":
            sheet.update_cell(row_number, col_index, f"Checked in At ({checkin_time})")
            return {"success": True, "order_code": order_code, "ticket_no": ticket_no}
        else:
            return {"success": False, "message": "Vé này đã được check-in rồi"}

    except gspread.CellNotFound:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy '{order_code}' trong sheet")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi check-in: {e}")
