-- 修正訂閱者表的 schema，允許同一個 Line User ID 訂閱多個類別
-- 請在 Supabase SQL Editor 中執行此腳本

-- 步驟 1: 移除舊的 UNIQUE 約束
ALTER TABLE subscribers DROP CONSTRAINT IF EXISTS subscribers_line_user_id_key;

-- 步驟 2: 建立複合唯一鍵（line_user_id + subscribed_category）
-- 這樣同一個 Line User ID 可以訂閱不同類別，但不能重複訂閱同一類別
ALTER TABLE subscribers 
ADD CONSTRAINT subscribers_line_user_id_category_unique 
UNIQUE (line_user_id, subscribed_category);

-- 驗證結果
SELECT 
    constraint_name, 
    constraint_type 
FROM information_schema.table_constraints 
WHERE table_name = 'subscribers';

-- 完成後，請重新執行 main.py 來同步訂閱者資料
