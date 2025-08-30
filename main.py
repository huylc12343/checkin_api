import os
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from fastapi.middleware.cors import CORSMiddleware

# --- Cấu hình ---
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # hoặc ["http://localhost:3000"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

SPREADSHEET_ID = "1D-LIdRIvcGN2R4sti-fCSp7tKcSBkXCTQnvmnXOWaCk"

SERVICE_ACCOUNT_FILE = "credentials.json"
creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
client = gspread.authorize(creds)
sheet = client.open_by_key(SPREADSHEET_ID).sheet1



@app.get("/find-data")
def data_found(key: str):
    try:
        extracted_key = key.removeprefix("SG")
        ticket_no = int(key[-1])  # số thứ tự vé (1-5)

        # Map số vé sang cột
        col_map = {
            1: 21,  # U
            2: 22,  # V
            3: 23,  # W
            4: 24,  # X
            5: 25   # Y
        }
        col_index = col_map.get(ticket_no)
        if not col_index:
            return {"found": False, "message": "Chỉ hỗ trợ vé số 1-5"}

        # Bỏ ký tự cuối cùng (ticket_no) để lấy order_code
        extracted_key = extracted_key[:-1]

        # Tìm dòng chứa order_code
        cell = sheet.find(extracted_key)
        row_number = cell.row
        row = sheet.row_values(row_number)

        # Lấy giá trị ô check-in
        checkin_value = sheet.cell(row_number, col_index).value 

        # Xác định trạng thái
        if checkin_value == "null":  # ô trống
            status = "unavailable"
            checkin_time = None

        elif checkin_value.lower() == "available":
            status = "available"
            checkin_time = None
        else:
            status = "checked_in"
            checkin_time = checkin_value  # chính là chuỗi "Checked in At (...)"


        return {
            "found": True,
            "order_code":key,
            "status": status,
            "checkin_time": checkin_time,
            "row_number": row_number,
            "ticket_no": ticket_no,
            "values": row
        }

    except Exception as e:
        return {
            "found": False,
            "status": status,
            "checkin_time": checkin_time,
            "message": f"Không tìm thấy '{key}' trong sheet. Lỗi: {e}"
        }

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

        # Bỏ ký tự cuối cùng để lấy order_code thực sự
        extracted_key = extracted_key[:-1]

        # Tìm mã vé trong sheet
        cell = sheet.find(extracted_key)
        row_number = cell.row

        # Map số vé sang cột (Checkin_1 = U = 21)
        col_map = {1: 21, 2: 22, 3: 23, 4: 24, 5: 25}
        col_index = col_map[ticket_no]

        # Ghi dữ liệu check-in
        checkin_time = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        cell_value = sheet.cell(row_number, col_index).value

        if not cell_value or cell_value.lower() == "available":
            sheet.update_cell(row_number, col_index, f"Checked in At ({checkin_time})")
        else:
            return {"success": False, "message": "Vé này đã được check-in rồi"}

        return {"success": True, "order_code": order_code, "ticket_no": ticket_no}

    except gspread.CellNotFound:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy '{order_code}' trong sheet")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi khi check-in: {e}")

    try:
        extracted_key = order_code.removeprefix("SG")
        ticket_no = int(order_code[-1])
        # Tìm mã vé trong sheet
        cell = sheet.find(extracted_key)
        row_number = cell.row

        # Map số vé sang cột (ví dụ Checkin_1 = U = 21)
        col_map = {
            1: 21,  # U
            2: 22,  # V
            3: 23,  # W
            4: 24,  # X
            5: 25   # Y
        }
        col_index = col_map.get(ticket_no)
        if not col_index:
            raise HTTPException(status_code=400, detail="Chỉ hỗ trợ checkin 1-5")

        # Ghi dữ liệu "x" + thời gian
        checkin_time = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

        cell_value = sheet.cell(row_number, col_index).value
        if not cell_value or cell_value.lower() == "available":
            sheet.update_cell(row_number, col_index, f"Checked in At ({checkin_time})")
        else:
            return {"success": False, "message": "Vé này đã được check-in rồi"}
        return {
            "success": True,
            "order_code": order_code,
            "ticket_no": ticket_no,
        }

    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Lỗi khi check-in: {e}")