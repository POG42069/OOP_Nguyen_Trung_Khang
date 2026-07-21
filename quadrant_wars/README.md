# Quadrant Wars

## Cập nhật sau vấn đáp

- Phím quân sự (phím thứ hai của mỗi người chơi) mở menu `Tấn công / Gọi quân về / Quay lại`.
- Trong `Gọi quân về`, phím thứ nhất đổi đạo quân, phím thứ hai ra lệnh quay về và phím thứ ba quay lại. Chỉ đạo quân còn đang hành quân mới hủy được; quân đã vào trận không thể hủy.
- Sông, núi và tường thành dọc biên giới là địa hình không thể đi qua. Mỗi cặp lãnh thổ kề nhau có một cổng; A* chọn tuyến ngắn nhất qua cổng và bước rút gọn waypoint không đi xuyên vật cản.
- `core/marching.py` quản lý đạo quân; `core/terrain.py` quản lý địa hình/tường/cổng; `core/navigation.py` tìm đường; `ui/map_features.py` vẽ bản đồ. `game_manager.py` chỉ điều phối trận đấu.

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

- Menu: chọn 2-4 slot, dùng hai nút mũi tên để đổi `Người`/`Bot`, rồi bấm bắt đầu trận.
- Player 1: `Q/W/E`; Player 2: `I/O/P`; Player 3: `Z/X/C`; Player 4: `B/N/M`.
- Ở trạng thái thường: phím 1 mở tuyển quân, phím 2 mở tấn công, phím 3 mở Strategy.
- Tuyển quân: phím 1 chuyển vùng đang sở hữu, phím 2 đổi Soldier/Worker/Cancel, phím 3 xác nhận.
- Tấn công: chọn mục tiêu bằng ba phím, sau đó chọn `0%` để hủy hoặc điều `33%`/`66%`; mỗi vùng luôn giữ lại ít nhất một Soldier.
- Strategy: phím 1 mở Development, phím 2 tranh mục tiêu trung lập đang hoạt động, phím 3 hủy.
- Development: phím 1 đổi vùng, phím 2 đổi Economy/Barracks/Fortress/Cancel, phím 3 xác nhận.
- `Esc` mở menu tạm dừng. Menu chính và Pause đều có nút `CẨM NANG`.

## Chuyên môn hóa lãnh thổ

- Mỗi vùng sống còn tự tạo 0.30 vàng/giây; mỗi Worker cộng thêm 0.40 vàng/giây.
- `Economy`: tăng 15% phần thu nhập do Worker tạo ra và giảm 8% giá Worker mới mỗi cấp; không nhân khoản thu nhập cơ bản.
- `Barracks`: Soldier rẻ hơn 2 vàng và thời gian huấn luyện giảm 20% mỗi cấp (`12/10` vàng, `1.04/0.78` giây).
- `Fortress`: thêm 2 Vệ binh và giảm 6% sát thương nhận vào cho toàn bộ lực lượng phòng thủ mỗi cấp.
- Xây cấp I tốn 30 vàng cục bộ, cấp II tốn 55 vàng; đổi nhánh tốn 40 vàng và quay lại cấp I.
- Khi lãnh thổ bị chiếm, công trình giảm một cấp. Cấp I thành phế tích nhưng vẫn giữ nhánh để chủ mới có thể sửa lại.
- Vệ binh có 18 HP, 3 damage, 0.8 đòn/giây; hồi 1 HP/giây ngoài trận và hồi sinh sau 45 giây. Vệ binh không thể tuyển hoặc điều đi tấn công.

## Mục tiêu trung lập

- Báo trước ở giây 110, mục tiêu đầu tiên hoạt động ở giây 120 và tồn tại cho đến khi bị chiếm.
- Sau khi được chiếm, đợt tiếp theo chờ 120 giây và báo trước 10 giây.
- `Caravan` cộng 30 vàng cho thủ đô, `War Banner` tăng 18% sát thương/tốc độ hành quân trong 30 giây, `Ancient Shrine` hồi 28 HP cho mọi Queen còn sống.
- Mục tiêu có 4 lính gác và một lõi 30 HP. Quân còn sống tự quay về sau khi hoàn thành.
- Khi nhiều phe cùng đến, Player đánh FFA trước; lính gác tạm rút lui, bất tử và giữ nguyên HP. Phe cuối cùng tiếp tục đánh NPC mà không được hồi máu.

## Đồ họa

- Chiến trường và ảnh nền menu dùng artwork bitmap được tạo riêng cho dự án.
- Soldier combat dùng atlas v2 bốn hướng với `idle` 4 frame, `run` 8, `attack` 8, `hit` 4 và `death` 6; Worker, Queen và Fortress dùng artwork cùng phong cách.
- Defender combat dùng atlas riêng với giáo, khiên, tuần tra cổng, đâm giáo, trúng đòn và tử trận.
- Animation chạy theo delta time và state machine, có nhún bước, nghiêng người, anticipation, lunge, impact, recovery, recoil và hit-flash.
- Map logic 1280x720 tự co theo cửa sổ; A* dẫn đội hình theo đường ngắn nhất quanh lâu đài, công trình, sông, núi và qua cổng tường biên giới.
- Điều X Soldier sẽ hiển thị đúng X sprite; từng lính tự áp sát, khóa mục tiêu, bao vây quân phòng thủ rồi chuyển sang đánh lâu đài.
- Hiệu ứng hành quân không vẽ đường chỉ dẫn; giao tranh có khói, lửa, bụi, tia lửa, vệt chém và phép trượng trực tiếp trên bản đồ.
- Bốn phe dùng bốn phong cách lâu đài riêng: Western Highland, Northern River, Forest Realm và Sun Court.
- Sông có water mask và dải phản quang chạy theo hướng dòng chảy; biên giới có tường đá và một cổng cho mỗi cặp lãnh thổ kề nhau.
- HUD trên cùng tổng hợp vàng, Soldier và Worker của từng người chơi, kể cả Soldier đang hành quân hoặc giao tranh.

## Giả định thiết kế

- Lính hành quân theo tổng chiều dài tuyến waypoint đến cổng lâu đài, không tới tức thời.
- Queen và Worker bị khóa ở lãnh thổ nhà.
- Khi Queen của một người chơi bị hạ, người chơi đó bị loại. Vùng vừa chiếm đổi sang chủ mới, có Queen mới, giữ Worker cũ và giữ lính sống sót làm quân đồn trú.
- Queen hồi máu tự nhiên khi không giao tranh; Fortress tập trung vào Vệ binh và giảm sát thương phòng thủ, không tăng hồi máu Queen.

## Cẩm nang và vòng đời UI

- Cẩm nang tiếng Việt có 5 trang: luật chơi, đơn vị, development, mục tiêu trung lập và điều khiển.
- Mỗi trang dùng sa bàn animation tự chạy và lấy số liệu trực tiếp từ `balance_config.py`.
- Trận đấu đi qua Intro 3-2-1; Pause dùng nền trận làm mờ; tiếp tục có đếm ngược riêng và không làm Match chạy ngầm.
- Chơi lại từ Pause giữ seed/map. Đấu lại từ màn kết quả giữ cấu hình Human/Bot nhưng tạo seed/map mới.
- Màn kết quả hiển thị thời lượng, lãnh thổ, Soldier, Worker và số mục tiêu từng Player đã chiếm.

## Cấu trúc OOP

- `core/unit.py`: `Unit` abstract base class, `Queen`, `Worker`, `Soldier`, `Defender` và state HP riêng của từng chiến binh.
- `core/territory.py`: đóng gói food, unit stacks, mua quân, HP và trạng thái lãnh thổ.
- `core/battlefield.py`: hình học sông, vị trí lâu đài và vị trí công trình dùng chung.
- `core/terrain.py`: dữ liệu sông, núi, tường biên giới và cổng dùng chung cho game/render.
- `core/marching.py`: trạng thái và chuyển động của đạo quân đang hành quân.
- `core/navigation.py`: `BattlefieldNavigator` đóng gói A*, obstacle và waypoint.
- `core/battle_arena.py`: từng `BattleAgent`, FFA fixed-step, công thành, tiếp viện và kết quả trận.
- `core/combat.py`: facade `CombatResolver.resolve_instant()`/`apply_result()` dùng chung engine realtime.
- `core/player.py`: `Player` abstract, `HumanPlayer`, `BotPlayer`, `BotStrategy` và 3 chiến thuật bot.
- `game/states.py`: State Pattern cho menu, tutorial, intro, playing, pause, resume countdown, transition và game over.
- `ui/renderer.py`: renderer Pygame tách khỏi logic core.
- `ui/map_features.py`: vẽ núi, tường biên giới và cổng từ dữ liệu `TerrainMap`.
- `ui/tutorial.py`: cẩm nang động và sa bàn minh họa.

## Test và mô phỏng cân bằng

```powershell
python -m unittest discover -s quadrant_wars\tests
python quadrant_wars\simulation\balance_sim.py --matches 100 --players 2 3 4
python -m quadrant_wars.simulation.combat_benchmark
```

`balance_config.py` chứa toàn bộ hằng số gameplay và ghi chú changelog cân bằng.
