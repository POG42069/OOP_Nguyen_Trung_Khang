# Quadrant Wars

Game đồ án OOP bằng Python 3 + Pygame, triển khai theo mô tả trong `agent.md` và file Word đề xuất.

## Cách chạy

```powershell
pip install -r requirements.txt
python -m quadrant_wars.main
```

Hoặc:

```powershell
python quadrant_wars\main.py
```

## Điều khiển

- Menu: chọn 2-4 slot, dùng hai nút mũi tên để đổi `Human`/`Bot`, rồi bấm `Start Battle`.
- Player 1: `Q/W/E`; Player 2: `I/O/P`; Player 3: `Z/X/C`; Player 4: `B/N/M`.
- Ở trạng thái thường: phím 1 mở tuyển quân, phím 2 mở tấn công, phím 3 mở Strategy.
- Tuyển quân: phím 1 chuyển vùng đang sở hữu, phím 2 đổi Soldier/Worker/Cancel, phím 3 xác nhận.
- Tấn công: chọn mục tiêu bằng ba phím, sau đó chọn `33%`, `66%` hoặc toàn bộ đội hình.
- Strategy: phím 1 mở Development, phím 2 tranh mục tiêu trung lập đang hoạt động, phím 3 hủy.
- Development: phím 1 đổi vùng, phím 2 đổi Economy/Barracks/Fortress/Cancel, phím 3 xác nhận.
- `Esc` mở menu tạm dừng.

## Chuyên môn hóa lãnh thổ

- `Economy`: Worker tạo thêm 25% vàng mỗi cấp.
- `Barracks`: Soldier rẻ hơn 1 vàng và sinh nhanh hơn 15% mỗi cấp.
- `Fortress`: giảm 10% sát thương nhận vào, đồng thời Queen hồi nhanh hơn 20% mỗi cấp.
- Xây cấp I tốn 35 vàng cục bộ, cấp II tốn 65 vàng; đổi nhánh tốn 45 vàng và quay lại cấp I.
- Khi lãnh thổ bị chiếm, công trình giảm một cấp. Cấp I thành phế tích nhưng vẫn giữ nhánh để chủ mới có thể sửa lại.

## Mục tiêu trung lập

- Báo trước từ giây 52, mục tiêu đầu tiên hoạt động ở giây 60; mỗi mục tiêu tồn tại 45 giây.
- Sau khi được chiếm hoặc hết hạn, đợt tiếp theo xuất hiện sau 75 giây và báo trước 8 giây.
- `Caravan` cộng 35 vàng cho thủ đô, `War Banner` tăng 15% sát thương/tốc độ hành quân trong 25 giây, `Ancient Shrine` hồi 35 HP cho mọi Queen còn sống.
- Mục tiêu có 3 lính gác và một lõi 24 HP. Quân còn sống tự quay về sau khi hoàn thành hoặc khi objective hết hạn.

## Đồ họa

- Chiến trường và ảnh nền menu dùng artwork bitmap được tạo riêng cho dự án.
- Soldier, Worker và Queen dùng sprite-sheet 2.5D riêng cho `idle`, `walk`, `attack`/`work`; Fortress dùng artwork cùng phong cách.
- Animation chạy theo delta time và state machine, có nhún bước, nghiêng người, anticipation, lunge, impact, recovery, recoil và hit-flash.
- Hiệu ứng hành quân không vẽ đường chỉ dẫn; giao tranh có khói, lửa, bụi, tia lửa, vệt chém và phép trượng trực tiếp trên bản đồ.
- Bốn phe dùng bốn phong cách lâu đài riêng: Western Highland, Northern River, Forest Realm và Sun Court.
- Sông có water mask và dải phản quang chạy theo hướng dòng chảy; biên giới dùng đường cong hữu cơ nhiều lớp thay cho nét đen thẳng cứng.
- HUD trên cùng tổng hợp vàng, Soldier và Worker của từng người chơi, kể cả Soldier đang hành quân hoặc giao tranh.

## Giả định thiết kế

- Lính hành quân theo khoảng cách giữa tâm 2 lãnh thổ, không tới tức thời.
- Queen và Worker bị khóa ở lãnh thổ nhà.
- Khi Queen của một người chơi bị hạ, người chơi đó bị loại. Vùng vừa chiếm đổi sang chủ mới, có Queen mới, giữ Worker cũ và giữ lính sống sót làm quân đồn trú.
- Queen hồi máu tự nhiên khi không giao tranh; Fortress tăng tốc độ hồi máu này.

## Cấu trúc OOP

- `core/unit.py`: `Unit` abstract base class, `Queen`, `Worker`, `Soldier` override `update()` và `combat_value`.
- `core/territory.py`: đóng gói food, unit stacks, mua quân, HP và trạng thái lãnh thổ.
- `core/combat.py`: `CombatResolver` tách riêng để unit test.
- `core/player.py`: `Player` abstract, `HumanPlayer`, `BotPlayer`, `BotStrategy` và 3 chiến thuật bot.
- `game/states.py`: State Pattern cho menu, playing, game over.
- `ui/renderer.py`: renderer Pygame tách khỏi logic core.

## Test và mô phỏng cân bằng

```powershell
python -m unittest discover -s quadrant_wars\tests
python quadrant_wars\simulation\balance_sim.py --matches 100 --players 2 3 4
```

`balance_config.py` chứa toàn bộ hằng số gameplay và ghi chú changelog cân bằng.

