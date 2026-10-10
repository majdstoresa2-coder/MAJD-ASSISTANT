from fastapi import FastAPI
from pydantic import BaseModel
import os

app = FastAPI(title='MAJD AI Engine')

class GenerateRequest(BaseModel):
    concept: str = 'Fantasy action RPG'
    category: str = 'RPG'

@app.get('/health')
def health():
    return {
        'ok': True,
        'service': 'majd-ai-engine',
        'port': int(os.getenv('PORT', '8000'))
    }

@app.post('/api/ai/generate')
def generate(req: GenerateRequest):
    return {
        'success': True,
        'concept': req.concept,
        'category': req.category,
        'title': 'Eclipse Dominion',
        'summary': 'A cinematic world with strategic combat, town building, and AI-driven story evolution.',
        'status': 'generated',
        'confidence': 0.96,
        'generated_assets': {
            'characters': ['Heroic Knight', 'Shadow Mage', 'Ancient Guardian'],
            'biomes': ['Frozen Ruins', 'Sunfire Outpost', 'Sky Citadel'],
            'mechanics': ['guild raids', 'upgrade loops', 'dynamic events']
        }
    }

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=int(os.getenv('PORT', '8000')))
