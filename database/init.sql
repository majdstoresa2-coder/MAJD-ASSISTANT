CREATE TABLE IF NOT EXISTS users (
  id UUID PRIMARY KEY,
  username VARCHAR(100) UNIQUE NOT NULL,
  email VARCHAR(255) UNIQUE NOT NULL,
  role VARCHAR(50) DEFAULT 'player',
  coins BIGINT DEFAULT 0,
  level INT DEFAULT 1,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS games (
  id UUID PRIMARY KEY,
  title VARCHAR(255) NOT NULL,
  slug VARCHAR(255) UNIQUE NOT NULL,
  category VARCHAR(100) NOT NULL,
  status VARCHAR(50) DEFAULT 'published',
  rating NUMERIC(3,1) DEFAULT 0.0,
  price NUMERIC(10,2) DEFAULT 0.0,
  downloads BIGINT DEFAULT 0,
  banner_url TEXT,
  description TEXT,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS orders (
  id UUID PRIMARY KEY,
  user_id UUID REFERENCES users(id),
  game_id UUID REFERENCES games(id),
  amount NUMERIC(10,2) DEFAULT 0.0,
  status VARCHAR(50) DEFAULT 'paid',
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS reviews (
  id UUID PRIMARY KEY,
  user_id UUID REFERENCES users(id),
  game_id UUID REFERENCES games(id),
  rating INT CHECK (rating BETWEEN 1 AND 5),
  comment TEXT,
  created_at TIMESTAMP DEFAULT NOW()
);
