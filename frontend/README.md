# IntelliGraph frontend

This React/Vite frontend is connected to the FastAPI backend in `../backend`.

## Run locally

Start the backend from the project root:

```powershell
venv\Scripts\python.exe -m uvicorn backend.main:app --reload --env-file .env
```

Then start the frontend in this folder:

```powershell
npm install
npm run dev
```

The frontend uses `http://localhost:8000` by default. To use another backend,
create `frontend/.env.local` with:

```text
VITE_API_BASE_URL=http://localhost:8000
```

Connected flows include document loading/upload/removal, topic/entity/document
graph rendering, factual/thematic query routing, grounded sources, and
evidence-path highlighting.

## API integration

The API client is in `src/api.js`; the UI calls `/api/documents`,
`/api/documents/upload`, `/api/graph`, and `/api/query`.

This template provides a minimal setup to get React working in Vite with HMR and some ESLint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Oxc](https://oxc.rs)
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/)

## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the ESLint configuration

If you are developing a production application, we recommend using TypeScript with type-aware lint rules enabled. Check out the [TS template](https://github.com/vitejs/vite/tree/main/packages/create-vite/template-react-ts) for information on how to integrate TypeScript and [`typescript-eslint`](https://typescript-eslint.io) in your project.
