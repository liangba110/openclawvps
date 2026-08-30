# Review System v2 — Multi-Dimensional Ratings + Complaints + Credit Score

## Tables Created

```sql
-- Main review table upgraded
ALTER TABLE review ADD COLUMN skill_rating TINYINT DEFAULT 5 AFTER rating;
ALTER TABLE review ADD COLUMN comm_rating TINYINT DEFAULT 5 AFTER skill_rating;
ALTER TABLE review ADD COLUMN attitude_rating TINYINT DEFAULT 5 AFTER comm_rating;
ALTER TABLE review ADD COLUMN is_anonymous TINYINT DEFAULT 0 AFTER content;
ALTER TABLE review ADD COLUMN images VARCHAR(1000) DEFAULT "" AFTER is_anonymous;
ALTER TABLE review ADD COLUMN useful_count INT DEFAULT 0 AFTER images;
ALTER TABLE review ADD COLUMN status TINYINT DEFAULT 1 AFTER useful_count;

-- Review replies (companion/admin respond to reviews)
CREATE TABLE review_reply (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    review_id INT UNSIGNED NOT NULL,
    user_id INT UNSIGNED NOT NULL,
    content VARCHAR(500) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_review (review_id)
);

-- Useful voting (toggle, one per user per review)
CREATE TABLE review_vote (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    review_id INT UNSIGNED NOT NULL,
    user_id INT UNSIGNED NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_review_user (review_id, user_id)
);

-- User complaints
CREATE TABLE complaint (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id INT UNSIGNED NOT NULL,
    target_type VARCHAR(20) DEFAULT 'companion',
    target_id INT UNSIGNED NOT NULL,
    order_id INT UNSIGNED DEFAULT 0,
    complaint_type VARCHAR(50) DEFAULT '',
    content TEXT NOT NULL,
    images VARCHAR(1000) DEFAULT "",
    status TINYINT DEFAULT 0,
    admin_reply TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Credit score change log
CREATE TABLE credit_log (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    companion_id INT UNSIGNED NOT NULL,
    change_amount INT NOT NULL,
    reason VARCHAR(100) DEFAULT '',
    order_id INT UNSIGNED DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE companion ADD COLUMN credit_score INT DEFAULT 100;
ALTER TABLE companion ADD COLUMN badges VARCHAR(200) DEFAULT '';
```

## API Endpoints (`review.py`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/review/submit` | Submit/update review. Body: `{order_id, rating, skill_rating, comm_rating, attitude_rating, content, is_anonymous, images}` |
| GET | `/api/review/list` | List reviews. Params: `companion_id, user_id, rating(5/1/0), sort(time/rating/useful), page, page_size` |
| POST | `/api/review/reply` | Companion reply. Body: `{review_id, content}` |
| POST | `/api/review/useful` | Toggle useful vote. Body: `{review_id}` |
| POST | `/api/review/complaint` | Submit complaint. Body: `{target_type, target_id, order_id, complaint_type, content, images}` |

## Auto-Scoring Logic

```python
def _update_companion_score(cursor, companion_id):
    cursor.execute("SELECT AVG(rating) as avg_r FROM review WHERE companion_id=%s AND status=1", (companion_id,))
    row = cursor.fetchone()
    if row and row['avg_r']:
        new_score = round(float(row['avg_r']), 1)
        credit_change = int((new_score - 3) * 10)
        cursor.execute("UPDATE companion SET credit_score=GREATEST(0, credit_score + %s) WHERE id=%s", (credit_change, companion_id))
        cursor.execute("INSERT INTO credit_log (companion_id, change_amount, reason) VALUES (%s,%s,'评价更新')", (companion_id, credit_change))
    cursor.execute("UPDATE user u JOIN companion c ON u.id=c.user_id SET u.score=%s WHERE c.id=%s", (new_score if row and row['avg_r'] else 5.0, companion_id))
```

## Admin Panel

`AdminReviews.vue` — dual tab layout:
- **评价管理:** filter (all/good/bad), hide/show/delete reviews
- **投诉处理:** list complaints with status badges, reply input, process/reject buttons
