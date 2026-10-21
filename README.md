# DocuMind

![CI](https://github.com/zahidrafid/documind/actions/workflows/ci.yml/badge.svg)
**Live demo:** https://documind-abrar.onrender.com — click "Try the demo account".
(Free hosting: the first load after a quiet period can take up to a minute.)


AI document assistant that answers questions from uploaded documents, with page-level citations.

## Tech stack
Django REST Framework · React · PostgreSQL + pgvector · OpenAI API · Docker

## Status
Deployed on Render (Docker) with Neon Postgres + pgvector, Redis and Celery. 51 automated tests run on every push.