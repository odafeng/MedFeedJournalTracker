-- Journal Tracker - Supabase Database Schema
-- 請在 Supabase SQL Editor 中執行此腳本

-- ============================================
-- Table 1: journals (期刊表)
-- ============================================
CREATE TABLE journals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    issn TEXT,
    url TEXT NOT NULL,
    rss_url TEXT,
    publisher_type TEXT NOT NULL, -- 'ieee', 'nature', 'elsevier', 'annual_reviews'
    scraper_class TEXT NOT NULL,   -- 對應的爬蟲類別名稱
    category TEXT NOT NULL,        -- 'CRC' 或 'SDS'
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 索引
CREATE INDEX idx_journals_category ON journals(category);
CREATE INDEX idx_journals_issn ON journals(issn);

-- ============================================
-- Table 2: subscribers (訂閱者表)
-- ============================================
CREATE TABLE subscribers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    line_user_id TEXT NOT NULL UNIQUE,
    subscribed_category TEXT NOT NULL, -- 'CRC' 或 'SDS'
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 索引
CREATE INDEX idx_subscribers_category ON subscribers(subscribed_category);
CREATE INDEX idx_subscribers_line_user_id ON subscribers(line_user_id);

-- ============================================
-- Table 3: articles (文章表)
-- ============================================
CREATE TABLE articles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    journal_id UUID REFERENCES journals(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    doi TEXT UNIQUE NOT NULL,  -- 用於去重
    url TEXT NOT NULL,
    published_date DATE,
    authors TEXT,
    abstract TEXT,
    category TEXT NOT NULL,    -- 繼承自期刊的類別 'CRC' 或 'SDS'
    discovered_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 索引
CREATE INDEX idx_articles_journal_id ON articles(journal_id);
CREATE INDEX idx_articles_doi ON articles(doi);
CREATE INDEX idx_articles_discovered_at ON articles(discovered_at);
CREATE INDEX idx_articles_category ON articles(category);

-- ============================================
-- Table 4: notifications (通知記錄表)
-- ============================================
CREATE TABLE notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    article_id UUID REFERENCES articles(id) ON DELETE CASCADE,
    subscriber_id UUID REFERENCES subscribers(id) ON DELETE CASCADE,
    sent_at TIMESTAMPTZ DEFAULT NOW(),
    status TEXT DEFAULT 'success', -- 'success', 'failed'
    error_message TEXT
);

-- 索引
CREATE INDEX idx_notifications_article_id ON notifications(article_id);
CREATE INDEX idx_notifications_subscriber_id ON notifications(subscriber_id);

-- ============================================
-- 完成
-- ============================================
-- 資料表建立完成！
-- 接下來請執行 Python 程式同步期刊和訂閱者資料。
