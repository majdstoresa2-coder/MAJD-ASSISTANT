import express from 'express';
import cors from 'cors';
import dotenv from 'dotenv';
import { v4 as uuidv4 } from 'uuid';

dotenv.config();

const app = express();
const PORT = process.env.PORT || 4000;

app.use(cors());
app.use(express.json());

const games = [
  {
    id: 'game-001',
    title: 'Dragon Slayer',
    slug: 'dragon-slayer',
    category: 'RPG',
    status: 'published',
    rating: 4.9,
    price: 29.99,
    downloads: 125000,
    bannerUrl: 'https://images.unsplash.com/photo-1511512578047-dfb367046420?auto=format&fit=crop&w=1200&q=80',
    description: 'A fantasy journey with dragon battles and world-building gameplay.',
    tags: ['fantasy', 'action', 'rpg'],
    featured: true
  },
  {
    id: 'game-002',
    title: 'Sky Command',
    slug: 'sky-command',
    category: 'Strategy',
    status: 'published',
    rating: 4.8,
    price: 19.99,
    downloads: 98000,
    bannerUrl: 'https://images.unsplash.com/photo-1542751371-adc38448a05e?auto=format&fit=crop&w=1200&q=80',
    description: 'Command elite pilots in a futuristic air war with tactical missions.',
    tags: ['strategy', 'air', 'tactical'],
    featured: true
  },
  {
    id: 'game-003',
    title: 'Pixel Origins',
    slug: 'pixel-origins',
    category: 'Adventure',
    status: 'published',
    rating: 4.7,
    price: 14.99,
    downloads: 64000,
    bannerUrl: 'https://images.unsplash.com/photo-1526509867165-5c4b1d5d5c6f?auto=format&fit=crop&w=1200&q=80',
    description: 'Explore a magical open world and rediscover your lost memories.',
    tags: ['adventure', 'story', 'exploration'],
    featured: false
  }
];

const users = [
  {
    id: 'user-001',
    username: 'MajdPlayer',
    email: 'player@majdgames.com',
    role: 'player',
    coins: 2500,
    level: 15,
    createdAt: new Date().toISOString()
  }
];

const leaderboard = [
  { name: 'Majd', score: 28400 },
  { name: 'Dragon', score: 27600 },
  { name: 'Rusher', score: 24950 },
  { name: 'Nova', score: 21300 }
];

app.get('/api/health', (req, res) => {
  res.json({ ok: true, service: 'majd-games-backend', time: new Date().toISOString() });
});

app.get('/api/games', (req, res) => {
  res.json({ success: true, data: games });
});

app.get('/api/games/:id', (req, res) => {
  const game = games.find((item) => item.id === req.params.id || item.slug === req.params.id);

  if (!game) {
    return res.status(404).json({ success: false, error: 'GAME_NOT_FOUND' });
  }

  return res.json({ success: true, data: game });
});

app.get('/api/users', (req, res) => {
  res.json({ success: true, data: users });
});

app.get('/api/leaderboard', (req, res) => {
  res.json({ success: true, data: leaderboard });
});

app.get('/api/admin/stats', (req, res) => {
  res.json({
    success: true,
    data: {
      totalUsers: users.length,
      totalGames: games.length,
      totalDownloads: games.reduce((sum, game) => sum + game.downloads, 0),
      revenue: games.reduce((sum, game) => sum + game.price * 210, 0).toFixed(2),
      activePlayers: 14840,
      aiGenerated: 26
    }
  });
});

app.post('/api/ai/generate', (req, res) => {
  const { concept, category } = req.body || {};

  const result = {
    success: true,
    concept: concept || 'Futuristic city defense',
    category: category || 'Action',
    title: 'Eclipse Dominion',
    summary: 'A cinematic strategy game where players defend floating cities against an alien swarm.',
    status: 'generated',
    confidence: 0.94,
    suggestion: {
      genre: 'Action RPG',
      environment: 'Neon city, frozen wasteland',
      playerLoop: 'explore, raid, upgrade, dominate'
    }
  };

  res.json(result);
});

app.post('/api/orders', (req, res) => {
  const { userId, gameId } = req.body || {};

  const order = {
    id: uuidv4(),
    userId: userId || 'user-001',
    gameId: gameId || 'game-001',
    amount: 29.99,
    status: 'paid',
    createdAt: new Date().toISOString()
  };

  res.status(201).json({ success: true, data: order });
});

app.listen(PORT, () => {
  console.log(`MAJD Games backend running on http://localhost:${PORT}`);
});
