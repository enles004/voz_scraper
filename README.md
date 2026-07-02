# voz-scraper

Công cụ thu thập các thread mới trên forum [voz.vn](https://voz.vn), mặc định là box [Chuyện trò linh tinh](https://voz.vn/f/chuyen-tro-linh-tinh%E2%84%A2.17/). Tool tự động bỏ qua bài ghim, lọc thread theo khoảng thời gian chỉ định và xuất kết quả ra file zip chứa JSON.

## Yêu cầu

- Python 3.10 trở lên
- [uv](https://docs.astral.sh/uv/) để quản lý môi trường và dependencies
- Các thư viện được khai báo trong `pyproject.toml`: `requests`, `beautifulsoup4`, `cloudscraper`, `lxml`

## Cài đặt

```bash
uv sync
```

Lệnh này tạo `.venv` và cài đầy đủ dependencies theo `pyproject.toml`.

## Sử dụng

Chạy với cấu hình mặc định (thread có hoạt động trong 6 giờ gần nhất):

```bash
uv run python main.py
```

Kết quả được ghi vào `voz_posts.zip` trong thư mục hiện tại.

## Tham số dòng lệnh

| Tham số | Mặc định | Mô tả |
|---|---|---|
| `--url` | box Chuyện trò linh tinh | URL của box cần thu thập |
| `--hours` | `6` | Chỉ lấy thread trong khoảng số giờ gần nhất |
| `--by` | `active` | `active`: lọc theo hoạt động cuối; `created`: lọc theo ngày tạo thread |
| `--output` | `voz_posts.zip` | Tên file zip đầu ra |
| `--max-pages` | `50` | Số trang tối đa được duyệt ở trang danh sách forum |
| `--workers` | `6` | Số luồng tải song song |
| `--rate` | `5.0` | Trần tốc độ toàn cục (số request mỗi giây) |
| `--retries` | `4` | Số lần thử lại mỗi request khi lỗi tạm thời |
| `--fresh` | tắt | Bỏ checkpoint cũ, chạy lại từ đầu |

Ví dụ:

```bash
# Lấy thread hoạt động trong 24 giờ, xuất ra file riêng
uv run python main.py --hours 24 --output voz_ngay.zip

# Lọc theo ngày tạo thread
uv run python main.py --by created --hours 12

# Thu thập một box khác
uv run python main.py --url "https://voz.vn/f/ten-box.99/"
```

## Định dạng đầu ra

File zip chứa `posts.json`, mỗi thread là một bản ghi:

```json
{
  "id": 1,
  "title": "Tiêu đề thread",
  "url": "https://voz.vn/t/...",
  "content": "Nội dung bài viết đầu tiên",
  "author": "username",
  "published_at": "2026-07-01T10:00:00+00:00",
  "comments": [
    {
      "author": "username_khac",
      "content": "Nội dung comment",
      "posted_at": "2026-07-01T10:05:00+07:00"
    }
  ],
  "tags": ["tag1", "tag2"]
}
```

Trường `content` là bài viết mở đầu; `comments` là toàn bộ bài trả lời của thread, lấy hết tất cả các trang không giới hạn. Trường `tags` chỉ xuất hiện khi thread có tag.

Nếu có trang nào không lấy được sau khi đã thử hết cách, zip sẽ kèm thêm `failures.json` liệt kê chính xác các URL bị thiếu để biết chỗ thủng.

## Chống lỗi mạng

Vì việc thu thập kéo dài và lấy rất nhiều trang, tool được thiết kế để chịu được sự cố mạng giữa chừng:

- **Thử lại thông minh:** mỗi request lỗi tạm thời (timeout, mất kết nối, `429`/`5xx`) được thử lại với thời gian chờ tăng dần và có nhiễu ngẫu nhiên; tôn trọng header `Retry-After`. Lỗi vĩnh viễn (vd `404`) thì bỏ ngay, không phí thời gian.
- **Tự chờ khi mất mạng hẳn:** nếu mất kết nối kéo dài, tool tạm dừng và dò mạng định kỳ, mạng về thì chạy tiếp thay vì bỏ hàng loạt trang.
- **Checkpoint/resume:** kết quả mỗi thread được ghi ra đĩa (`<output>.work/`) ngay khi xong. Nếu tiến trình chết giữa chừng, **chạy lại đúng lệnh cũ** sẽ bỏ qua các thread đã lấy và chỉ làm tiếp phần còn thiếu. Chạy xong sạch sẽ thì thư mục checkpoint tự xoá.
- **Quét lại + báo cáo:** các trang lỗi được quét lại một vài lượt cuối; trang nào vẫn hỏng thì ghi vào `failures.json` chứ không mất âm thầm.

## Cấu trúc dự án

```
main.py              Điểm vào của chương trình
src/
├── config.py        Hằng số và tham số cấu hình (ScrapeSettings)
├── models.py        Kiểu dữ liệu (ThreadMeta, ThreadRecord)
├── http_client.py   Tải trang, thử lại khi lỗi, giới hạn tốc độ (Fetcher, RateLimiter)
├── parsers.py       Bóc tách HTML thành dữ liệu có cấu trúc
├── crawler.py       Điều phối tải song song, phân trang, lọc, lấy comment (VozCrawler)
├── store.py         Checkpoint/resume theo từng thread (CheckpointStore)
├── exporters.py     Ghi kết quả và failures.json ra file zip
└── cli.py           Xử lý tham số dòng lệnh
```

## Ghi chú

- Tool luôn lấy **toàn bộ** comment của mỗi thread (mọi trang), phục vụ mục đích thu thập dữ liệu đầy đủ. Thread dài hàng trăm trang sẽ tốn nhiều request và thời gian.
- Các thread được tải song song (`--workers`), comment trong cùng một thread cũng được tải song song rồi ghép lại đúng thứ tự. Toàn bộ chịu chung một trần tốc độ `--rate` để tránh bị Cloudflare chặn.
- Tăng `--rate`/`--workers` sẽ nhanh hơn nhưng dễ bị chặn IP hơn; mặc định `6` luồng và `5` req/s là mức khá an toàn.
- Nếu voz.vn thay đổi giao diện dẫn đến không lấy được nội dung, cần cập nhật lại các selector trong `parsers.py`.
