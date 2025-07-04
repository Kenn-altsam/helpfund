# Ayala Foundation Backend API

A FastAPI backend service that helps charity foundations discover companies and sponsorship opportunities through AI-powered conversations.

## Features

- 🤖 AI-powered sponsorship matching using OpenAI
- 🚀 Fast and modern API built with FastAPI
- 📝 Comprehensive API documentation with Swagger/OpenAPI
- 🔄 CORS support for frontend integration
- ⚡ Async/await for optimal performance

## Project Structure

```
src/
├── main.py                 # FastAPI application entry point
├── core/
│   ├── __init__.py
│   └── config.py          # Configuration management
└── ai_conversation/
    ├── __init__.py
    ├── models.py          # Pydantic models
    ├── service.py         # OpenAI service
    └── router.py          # API endpoints
```

## Prerequisites

- Python 3.8+
- OpenAI API key

## Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd Ayala_app_back
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment setup**
   ```bash
   cp env.example .env
   ```
   
   Edit `.env` and add your OpenAI API key:
   ```
   OPENAI_API_KEY=your_openai_api_key_here
   ```

## Running the Application

1. **Start the development server**
   ```bash
   cd src
   uvicorn main:app --reload --host localhost --port 8000
   ```

2. **Access the API**
   - API Base URL: http://localhost:8000
   - Interactive API docs: http://localhost:8000/docs
   - ReDoc documentation: http://localhost:8000/redoc

## API Endpoints

### Core Endpoints

- `GET /` - API health check
- `GET /health` - Detailed health status

### AI Conversation

- `POST /api/v1/funds/conversation` - Send message to AI assistant
- `GET /api/v1/funds/conversation/health` - AI service health check

## Usage Examples

### AI Conversation

```bash
curl -X POST "http://localhost:8000/api/v1/funds/conversation" \
     -H "Content-Type: application/json" \
     -d '{
       "user_input": "I am looking for tech companies in Almaty that might sponsor education initiatives"
     }'
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "message": "I'd be happy to help you find tech companies in Almaty interested in education sponsorship..."
  },
  "message": "Conversation message processed successfully"
}
```

## Configuration

Environment variables (in `.env` file):

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key (required) | - |
| `HOST` | Server host | localhost |
| `PORT` | Server port | 8000 |
| `DEBUG` | Debug mode | True |
| `ALLOWED_ORIGINS` | CORS allowed origins | http://localhost:3000,http://127.0.0.1:3000 |

## Development

### Code Style

The project follows:
- PEP 8 for Python code style
- Type hints for all functions
- Comprehensive docstrings
- Modular architecture with clear separation

### Adding New Features

1. Create new modules in appropriate directories
2. Follow the established patterns for models, services, and routers
3. Update the main.py to include new routers
4. Add proper error handling and logging

## API Response Format

All API responses follow this standard format:

```json
{
  "status": "success|error",
  "data": { ... },
  "message": "Human-readable message"
}
```

## Error Handling

The API includes comprehensive error handling for:

- Invalid input validation
- OpenAI API errors
- Rate limiting
- Authentication errors
- Network issues

## Future Enhancements

This is a minimal version. Planned additions include:

- User authentication and authorization
- Company database integration
- Advanced AI conversation state management
- Location-based company search
- Comprehensive company profiles
- PostgreSQL database integration

## Contributing

1. Follow the existing code style and patterns
2. Add proper type hints and docstrings
3. Test your changes thoroughly
4. Update documentation as needed

## License

[License information here] 