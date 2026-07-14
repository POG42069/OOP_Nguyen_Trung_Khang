<p align="center">
  <img src="quadrant_wars/assets/images/battlefield.png" alt="Chiến trường Quadrant Wars" width="100%">
</p>

<h1 align="center">Quadrant Wars</h1>

<p align="center">
  <strong>Game chiến thuật thời gian thực về chinh phục lãnh thổ, xây dựng vương quốc và giao tranh trên bản đồ động.</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.10 trở lên">
  <img src="https://img.shields.io/badge/Pygame-2.5%2B-2D6E9E?style=for-the-badge" alt="Pygame 2.5 trở lên">
  <img src="https://img.shields.io/badge/Course-IT002%20OOP-1F7A5A?style=for-the-badge" alt="IT002 OOP">
  <img src="https://img.shields.io/badge/Players-2--4-D68A3A?style=for-the-badge" alt="2 đến 4 người chơi">
</p>

<p align="center">
  <a href="#thong-tin-do-an">Thông tin đồ án</a>
  &nbsp;|&nbsp;
  <a href="#tong-quan">Tổng quan</a>
  &nbsp;|&nbsp;
  <a href="#cai-dat-va-chay">Cài đặt</a>
  &nbsp;|&nbsp;
  <a href="#dieu-khien">Điều khiển</a>
  &nbsp;|&nbsp;
  <a href="#cau-truc-du-an">Kiến trúc</a>
</p>

---

<h2 id="thong-tin-do-an">Thông tin đồ án</h2>

| Hạng mục | Chi tiết |
| --- | --- |
| Môn học | IT002 - Lập trình hướng đối tượng |
| Lớp | TTNT2025 |
| Giảng viên | Phạm Nguyễn Trường An |
| Loại dự án | Đồ án nhóm |
| Ngôn ngữ | Python 3.10+ |
| Framework | Pygame 2.5+ |

### Thành viên nhóm

| Thành viên | MSSV |
| --- | --- |
| Nguyễn Minh Khang | 25520793 |
| Phạm Thành Trung | 25521970 |
| Nguyễn Cao Nguyên | 25521241 |

---

<h2 id="tong-quan">Tổng quan game</h2>

**Quadrant Wars** là game chiến thuật thời gian thực dành cho 2-4 người chơi hoặc bot. Mỗi lãnh thổ có vàng, Worker, Soldier, Queen, hàng chờ tuyển quân và công trình chuyên môn hóa riêng.

Mỗi phe khởi đầu với một thủ đô. Người chơi tuyển quân, phát triển từng vùng, tấn công đối thủ, tranh mục tiêu trung lập và tiêu diệt Queen của các phe còn lại để trở thành vương quốc sống sót cuối cùng.

### Vòng lặp gameplay

```text
Tuyển quân -> Phát triển lãnh thổ -> Hành quân và giao tranh -> Chiếm vùng
     ^                                                        |
     +------ Nhận vàng địa phương và phần thưởng mục tiêu ----+
```

### Tính năng chính

| Tính năng | Mô tả |
| --- | --- |
| 2-4 người chơi | Mỗi slot có thể là Human hoặc một trong ba chiến thuật bot. |
| Kinh tế theo lãnh thổ | Vùng chiếm được giữ vàng, Worker, Soldier, Queen HP và hàng chờ sản xuất độc lập. |
| Tuyển quân theo vùng | Chọn chính xác vùng sở hữu nào sẽ tuyển Soldier hoặc Worker; áp dụng cho cả bốn bộ phím điều khiển. |
| Chuyên môn hóa lãnh thổ | Xây Economy, Barracks hoặc Fortress với hai cấp nâng cấp và hiệu ứng cục bộ. |
| Mục tiêu trung lập | Tranh Caravan, War Banner và Ancient Shrine để đảo chiều nhịp độ trận đấu. |
| Combat thời gian thực | Đạo quân tự hành quân qua bản đồ, giao tranh tại combat zone và quay về sau khi xong mục tiêu. |
| Bot khác biệt | Aggressive, Balanced và Economic Bot có ưu tiên phát triển và chiến đấu khác nhau. |
| Đồ họa và âm thanh | Sông chảy, biên giới hữu cơ, lâu đài theo phe, sprite chuyển động, hiệu ứng chiến đấu và âm thanh sự kiện. |

---

## Chuyên môn hóa lãnh thổ

Mỗi lãnh thổ có thể được phát triển độc lập. Toàn bộ chi phí lấy từ vàng cục bộ của vùng đang nâng cấp.

| Nhánh | Hiệu ứng mỗi cấp |
| --- | --- |
| Economy | Worker tạo thêm 25% vàng. |
| Barracks | Soldier sinh nhanh hơn 15% và rẻ hơn 1 vàng. |
| Fortress | Lãnh thổ nhận ít hơn 10% sát thương, Queen hồi nhanh hơn 20%. |

- Xây cấp I tốn `35` vàng cục bộ.
- Nâng cấp II tốn `65` vàng cục bộ.
- Đổi sang nhánh khác tốn `45` vàng và quay lại cấp I.
- Khi bị chiếm, công trình mất một cấp. Công trình cấp I trở thành phế tích để chủ mới có thể sửa lại.

---

## Mục tiêu trung lập

Mục tiêu được cảnh báo trước khi xuất hiện, có lính gác trung lập và một lõi HP dùng chung. Mọi phe đều có thể đưa quân đến tranh chấp.

| Mục tiêu | Phần thưởng |
| --- | --- |
| Caravan | Cộng `35` vàng vào thủ đô hiện tại. |
| War Banner | Tăng 15% sát thương và tốc độ hành quân trong 25 giây. |
| Ancient Shrine | Hồi 35 HP cho toàn bộ Queen còn sống, không vượt quá máu tối đa. |

Mục tiêu đầu tiên kích hoạt ở giây thứ 60; các mục tiêu sau xuất hiện theo lịch hồi sau khi có phe chiếm được hoặc hết hạn.

---

<h2 id="cai-dat-va-chay">Cài đặt và chạy</h2>

### 1. Clone repository

```powershell
git clone https://github.com/POG42069/OOP_Nguyen_Trung_Khang.git
cd OOP_Nguyen_Trung_Khang
```

### 2. Tạo và kích hoạt môi trường ảo

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Cài thư viện

```powershell
pip install -r requirements.txt
```

### 4. Chạy game

```powershell
python -m quadrant_wars.main
```

Có thể chạy trực tiếp bằng `python quadrant_wars\main.py` từ thư mục gốc của repository.

---

<h2 id="dieu-khien">Điều khiển</h2>

Trong menu khởi đầu, đặt slot người chơi thành `Human` để bật bộ phím tương ứng.

| Player | Phím 1 | Phím 2 | Phím 3 |
| --- | --- | --- | --- |
| Player 1 | `Q` | `W` | `E` |
| Player 2 | `I` | `O` | `P` |
| Player 3 | `Z` | `X` | `C` |
| Player 4 | `B` | `N` | `M` |

| Trạng thái | Phím 1 | Phím 2 | Phím 3 |
| --- | --- | --- | --- |
| Bình thường | Mở Recruit | Chọn mục tiêu tấn công | Mở Strategy |
| Recruit | Chuyển vùng sở hữu | Soldier -> Worker -> Cancel | Xác nhận lựa chọn |
| Chọn mục tiêu | Chọn mục tiêu | Chọn mục tiêu | Chọn mục tiêu hoặc hủy khi có thể |
| Chọn quân tấn công | Gửi 33% | Gửi 66% | Gửi toàn bộ Soldier |
| Strategy | Mở Development | Tranh mục tiêu trung lập đang hoạt động | Hủy |
| Development | Chuyển vùng sở hữu | Economy -> Barracks -> Fortress -> Cancel | Xác nhận lựa chọn |

Popup Recruit hiển thị vùng đang chọn, vàng cục bộ và chi phí trước khi xác nhận tuyển quân.

---

## Thiết kế hướng đối tượng

| Nguyên tắc hoặc pattern | Cách áp dụng |
| --- | --- |
| Encapsulation | `Territory` quản lý tài nguyên, đơn vị, hàng chờ và công trình của chính nó. |
| Inheritance và polymorphism | `Unit` được mở rộng bởi `Queen`, `Worker`, `Soldier`; `Player` được mở rộng bởi `HumanPlayer`, `BotPlayer`. |
| Strategy Pattern | Các Bot Strategy xác định phong cách kinh tế, cân bằng và tấn công. |
| State Pattern | Menu, trận đấu, pause, game over và menu lệnh của người chơi được biểu diễn bằng state. |
| Separation of concerns | Combat, quản lý trận, render, âm thanh và input được tách thành các module chuyên trách. |

---

<h2 id="cau-truc-du-an">Cấu trúc dự án</h2>

```text
OOP_Nguyen_Trung_Khang/
├── quadrant_wars/
│   ├── main.py                 # Entry point và vòng lặp Pygame
│   ├── balance_config.py       # Hằng số gameplay và cân bằng game
│   ├── core/
│   │   ├── combat.py           # Combat resolver và combat zone
│   │   ├── map_generator.py    # Sinh bản đồ lãnh thổ hữu cơ
│   │   ├── objective.py        # Mục tiêu trung lập
│   │   ├── player.py           # Human, bot và bot strategy
│   │   ├── territory.py        # Kinh tế, unit và specialization
│   │   └── unit.py             # Hệ thống unit
│   ├── game/
│   │   ├── game_manager.py     # Vòng đời trận, army, capture, reward
│   │   └── states.py           # State machine màn hình và input
│   ├── ui/
│   │   ├── art.py              # Load artwork và animation frame
│   │   ├── renderer.py         # Map, HUD, effect và animation
│   │   └── sound.py            # Phát âm thanh theo sự kiện
│   ├── assets/
│   │   ├── images/             # Bản đồ, lâu đài và artwork unit
│   │   └── sounds/             # Âm thanh tuyển quân, combat, objective
│   ├── simulation/             # Mô phỏng cân bằng headless
│   └── tests/                  # Unit test và gameplay-flow test
├── requirements.txt
└── README.md
```

---

## Kiểm thử và mô phỏng

Chạy unit test và mô phỏng cân bằng từ thư mục gốc:

```powershell
python -m unittest discover -s quadrant_wars\tests
python quadrant_wars\simulation\balance_sim.py --matches 100 --players 2 3 4
```

---

## Mục đích học thuật

Repository được phát triển cho đồ án nhóm môn **IT002 - Lập trình hướng đối tượng**, phục vụ mục đích học tập, trình diễn và nghiên cứu thiết kế phần mềm hướng đối tượng.
