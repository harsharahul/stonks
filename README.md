# 🚀 Stonks - Stock Analytics Platform

> **AI-Powered Stock Discovery with Real-Time Analytics, Signals, and Alerts**

## 📍 **🚨 IMPORTANT: START HERE FOR PROJECT INFORMATION**

**This project uses a consolidated documentation system. For complete project information, always start with:**

### **📋 [MASTER_DOCUMENTATION.md](./MASTER_DOCUMENTATION.md) ← CLICK HERE FIRST**

This master document contains:
- **Complete project overview and current status**
- **Navigation to all other documentation**
- **Current issues and next steps**
- **Quick start commands**
- **Project health status**

---

## 🎯 **Quick Project Overview**

Stonks is a comprehensive stock analytics platform that combines:
- **Real-time data ingestion** from multiple sources (SEC EDGAR, Reddit WSB, News RSS)
- **AI-powered analytics** with sentiment analysis and feature calculation
- **Automated signal generation** and real-time alerts
- **Interactive dashboard** with stock management and tracking
- **WebSocket real-time updates** for live market intelligence

## 🚀 **Quick Start**

```bash
# Clone and setup
git clone <repository>
cd Stonks

# Backend
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8080

# Frontend
cd frontend
npm run dev

# Celery Worker
celery -A app.worker worker --loglevel=info
```

## 📊 **Current Status**

- **Phase**: End-to-End Feature Hardening
- **Progress**: 86% Complete
- **Status**: Frontend sorting/filtering needs UI verification
- **Health**: 🟢 Backend APIs, 🟡 Frontend UI, 🟢 Database, 🟢 Real-time Features

## 🔗 **Essential Documentation Links**

| Document | Purpose | When to Use |
|----------|---------|-------------|
| **[MASTER_DOCUMENTATION.md](./MASTER_DOCUMENTATION.md)** | **Complete project overview** | **ALWAYS START HERE** |
| [PROJECT_CHECKPOINT.md](./PROJECT_CHECKPOINT.md) | Current status & next steps | Check current progress |
| [USER_STORIES_AND_FLOWS.md](./USER_STORIES_AND_FLOWS.md) | User experience & requirements | Understand user needs |
| [docs/architecture.md](./docs/architecture.md) | System architecture | Understand system design |
| [docs/implementation-notes.md](./docs/implementation-notes.md) | Technical details | Implementation guidance |

## 🛠️ **Tech Stack**

- **Backend**: FastAPI + PostgreSQL + Redis + Celery
- **Frontend**: React + TypeScript + Tailwind CSS + Vite
- **AI/ML**: OpenAI GPT-4 + LangGraph + Custom Analytics
- **Real-time**: WebSocket + Redis Pub/Sub
- **Data**: SEC EDGAR, Reddit WSB, News RSS, Earnings Calendar

## 🎯 **Key Features**

- ✅ **Stock Management**: Add/remove/track stocks with priority levels
- ✅ **Real-time Alerts**: WebSocket-powered live market alerts
- ✅ **AI Insights**: LLM-powered stock analysis and recommendations
- ✅ **Data Pipeline**: Automated ingestion from multiple financial sources
- ✅ **Feature Store**: Daily aggregated analytics with versioning
- ✅ **Toast Notifications**: User-friendly feedback system

## 🚨 **Known Issues**

- Frontend sorting/filtering UI updates need verification
- Real-time state management optimization needed

## 🔮 **Roadmap**

- **Phase 1**: Auto-removal for non-trending stocks
- **Phase 2**: Enhanced signal generation for user stocks
- **Phase 3**: Production hardening and deployment

---

## 📝 **For Developers**

### **Documentation Workflow**
1. **Always start with** [MASTER_DOCUMENTATION.md](./MASTER_DOCUMENTATION.md)
2. **Check current status** in [PROJECT_CHECKPOINT.md](./PROJECT_CHECKPOINT.md)
3. **Update checkpoint** when making changes
4. **Follow the documentation update workflow**

### **Code Standards**
- Python: Black formatting, type hints, docstrings
- Frontend: ESLint, Prettier, TypeScript strict mode
- Database: Alembic migrations, SQLAlchemy models
- Testing: pytest, Playwright for E2E

---

## 🤝 **Contributing**

1. Read [MASTER_DOCUMENTATION.md](./MASTER_DOCUMENTATION.md) first
2. Check [PROJECT_CHECKPOINT.md](./PROJECT_CHECKPOINT.md) for current status
3. Follow the established patterns and architecture
4. Update documentation as you progress

---

## 📞 **Support**

- **Project Status**: [PROJECT_CHECKPOINT.md](./PROJECT_CHECKPOINT.md)
- **Known Issues**: [KNOWN_ISSUES.md](./KNOWN_ISSUES.md)
- **User Stories**: [USER_STORIES_AND_FLOWS.md](./USER_STORIES_AND_FLOWS.md)

---

*This README provides a quick overview. For complete project information, documentation, and current status, always start with [MASTER_DOCUMENTATION.md](./MASTER_DOCUMENTATION.md).*


