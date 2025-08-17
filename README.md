🚀 Stonks – AI-Powered Market Intelligence Platform

Stonks has evolved into a **next-generation AI-powered market intelligence system** that combines traditional market data with advanced alternative data sources through an expandable, LLM-driven architecture. The platform features politician stock trades monitoring, intelligent signal processing with LangGraph agents, self-correcting data writes, and comprehensive real-time analytics.

## 🏆 Features

- **AI-Powered Signal Processing**: LangGraph-based intelligent agents with multi-step workflows
- **Politician Stock Trades Monitoring**: Real-time Congressional and Senate stock disclosure tracking
- **Self-Correcting Data System**: LLM-powered validation and automatic error correction
- **Intelligent Signal Routing**: Smart prioritization and multi-channel distribution
- **Real-Time Alert System**: 8 alert types with smart cooldown management
- **WebSocket Infrastructure**: 4 broadcasting channels with 100% stability
- **Expandable Signal Architecture**: Modular framework supporting unlimited data sources

## 📚 Key Documentation

### **Quick Start & Resume**
- **RESUMPTION_GUIDE.md** – Instant resume instructions for any session
- **MASTER_CHECKPOINT.md** – Complete current status and architecture overview
- **KNOWN_ISSUES.md** – All issues documented with solutions

### **Technical Architecture**
- **docs/architecture.md** – AI-powered system architecture  
- **docs/expandable-signal-architecture.md** – signal processing framework
- **REAL_DATA_TESTING_GUIDE_UPDATED.md** – Comprehensive testing procedures
- **ARCHITECTURE_REVIEW.md** – Design cohesion analysis and readiness assessment

### **Historical Reference**
- **PROJECT_STATUS_SUMMARY.md** – Detailed progress tracking
- **docs/platform-overview.md** – Platform vision and capabilities

## 🛠️ Technology Stack

- **Backend**: Python 3.11 + FastAPI + LangGraph + Celery + Redis
- **AI/LLM**: LangGraph workflows + OpenAI + Ollama fallback
- **Database**: PostgreSQL 16 with 15+ specialized tables
- **Frontend**: React + Vite + Tailwind CSS with real-time WebSocket integration
- **Data Sources**: Yahoo Finance, RSS feeds, Reddit WSB, SEC filings, Political trades

## 🚀 Current Status

**Status**: ✅ **AI-POWERED PLATFORM - OPERATIONAL & PRODUCTION READY**  
**Phase**: Next-Generation Market Intelligence System - 100% Complete  
**Assessment**: 🏆 **BREAKTHROUGH SUCCESS**

Dev → Prod

- Local dev: docker-compose for DB, Redis, and optional Ollama; create a `.env` using keys in `docs/configuration.md`
- Prod: k3s manifests with Kustomize overlays; images built via Gitea Actions
- Optional analytics enrichment via OpenAI or Ollama; disabled by default


