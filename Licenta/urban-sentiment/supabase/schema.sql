-- Create users table (maps to Auth0 users)
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    auth0_id TEXT UNIQUE NOT NULL,
    email TEXT NOT NULL,
    name TEXT,
    role TEXT DEFAULT 'Normal User', -- 'Normal User', 'Premium User', 'City Management User', 'Administrator'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Create feedbacks table (based on LiveFeed.jsx structure)
CREATE TABLE IF NOT EXISTS feedbacks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    author_name TEXT NOT NULL,
    author_initials TEXT NOT NULL,
    color TEXT DEFAULT 'slate',
    location TEXT NOT NULL,
    topic TEXT NOT NULL,
    content TEXT NOT NULL,
    sentiment_label TEXT,
    sentiment_score INTEGER,
    sentiment_color TEXT,
    sentiment_gradient TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Enable Row Level Security (RLS)
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE feedbacks ENABLE ROW LEVEL SECURITY;

-- Create basic RLS policies
-- Anyone can read feedbacks
CREATE POLICY "Feedbacks are viewable by everyone" ON feedbacks
    FOR SELECT USING (true);

-- Only authenticated users can insert feedbacks (placeholder policy)
CREATE POLICY "Authenticated users can create feedbacks" ON feedbacks
    FOR INSERT WITH CHECK (auth.role() = 'authenticated');
