# TraceBox — Spec de Migração de Frontend
**Versão:** 1.0  
**Data:** 2026-04-27  
**Status:** Proposta para aprovação

---

## 1. Contexto e Motivação

O TraceBox utiliza Streamlit como camada de apresentação. Streamlit foi projetado para prototipagem de dados e MVPs internos, não para sistemas enterprise com necessidade de:

- Temas em runtime (dark/light) — limitação estrutural: `st.dataframe()` renderiza em `<canvas>`, fora do alcance do CSS
- Grids de dados com customização total (ordenação, filtros avançados, edição inline)
- UX de nível enterprise (transições, feedback visual, responsividade completa)
- Escalabilidade de time (Streamlit não segue padrões de component-based development)
- Testes de frontend adequados (Playwright, Cypress, Testing Library)

O backend FastAPI + SQLAlchemy + PostgreSQL está bem estruturado e **não precisa ser reescrito**. A migração é exclusiva da camada de apresentação.

---

## 2. Módulos Existentes (Escopo da Migração)

| Módulo Streamlit         | Rota Proposta              | Complexidade |
|--------------------------|----------------------------|--------------|
| `views/auth.py`          | `/login`                   | Baixa        |
| `views/cadastro.py`      | `/cadastro`                | Média        |
| `views/produto.py`       | `/produtos`                | Média        |
| `views/parceiros.py`     | `/parceiros`               | Média        |
| `views/inbound.py`       | `/inbound`                 | Alta         |
| `views/outbound.py`      | `/outbound`                | Alta         |
| `views/inventario.py`    | `/inventario`              | Alta         |
| `views/matriz_fisica.py` | `/matriz-fisica`           | Alta         |
| `views/etiquetas.py`     | `/etiquetas`               | Média        |
| `views/fiscal.py`        | `/fiscal`                  | Alta         |
| `views/manutencao.py`    | `/manutencao`              | Alta         |
| `views/requisicao.py`    | `/requisicao`              | Média        |
| `views/auditoria.py`     | `/auditoria`               | Alta         |
| `views/torre_controle.py`| `/torre-controle`          | Alta         |
| `views/relatorios.py`    | `/relatorios`              | Média        |
| `views/configuracoes.py` | `/configuracoes`           | Média        |

---

## 3. Avaliação de Tecnologias

### 3.1 Candidatos

| Framework      | Ecossistema | Enterprise-ready | Curva | DevOps | Decisão   |
|----------------|-------------|------------------|-------|--------|-----------|
| Next.js 14+    | ★★★★★       | ★★★★★            | Média | Docker | ✅ **Escolhido** |
| Vue 3 + Nuxt 3 | ★★★★☆       | ★★★★☆            | Baixa | Docker | Alternativa |
| Angular 17+    | ★★★★☆       | ★★★★★            | Alta  | Docker | Descartado |
| SvelteKit      | ★★★☆☆       | ★★★☆☆            | Baixa | Docker | Descartado |

### 3.2 Por que Next.js 14+ (App Router)

1. **Ecosistema**: maior disponibilidade de componentes enterprise e de devs no mercado
2. **OpenAPI → TypeScript**: FastAPI gera `/openapi.json` nativo; `openapi-typescript` gera tipos automaticamente — zero tipagem manual
3. **Roteamento**: App Router com layouts aninhados — sidebar/header persistem sem re-render
4. **Rendering**: SSR/SSG onde aplicável, Client Components onde necessário
5. **Deploy**: `output: 'standalone'` gera container Docker sem Node.js runtime externo
6. **Grids**: TanStack Table v8 é headless — renderiza HTML puro, tema 100% controlável via CSS

---

## 4. Stack Definitivo

### 4.1 Frontend

```
Next.js 14+          — framework (App Router)
TypeScript 5+        — tipagem estática
Tailwind CSS 3+      — utility-first styling
shadcn/ui            — componentes (Radix UI + Tailwind, copy-paste, sem lock-in)
TanStack Query v5    — server state, caching, invalidação automática
TanStack Table v8    — grids headless, totalmente temáveis
React Hook Form v7   — gerenciamento de formulários
Zod v3               — validação de esquemas (compartilhável com backend via openapi)
Zustand v4           — client state (tema, user session, filtros globais)
next-themes          — dark/light toggle em runtime via CSS variables
Recharts v2          — gráficos (torre de controle, auditoria, dashboards)
openapi-typescript   — geração automática de tipos a partir do /openapi.json da API
```

### 4.2 Tooling de Desenvolvimento

```
Vitest               — testes unitários (componentes, hooks, utils)
Playwright           — testes E2E (fluxos críticos: login, inbound, fiscal)
ESLint + Prettier    — linting e formatação
Husky + lint-staged  — pre-commit hooks
```

### 4.3 Backend (sem alterações no core)

```
FastAPI              — mantido integralmente
SQLAlchemy 2.0       — mantido
PostgreSQL           — mantido
Alembic              — mantido
PyJWT + bcrypt       — mantido
```

**Único ajuste necessário no backend:** configurar CORS corretamente para aceitar requisições do domínio do frontend.

---

## 5. Arquitetura de Destino

```
tracebox/
├── api/                        # FastAPI (mantido)
│   └── endpoints.py
├── database/                   # SQLAlchemy (mantido)
├── repositories/               # (mantido)
├── services/                   # (mantido)
├── controllers/                # (mantido)
│
└── frontend/                   # NOVO — Next.js
    ├── app/
    │   ├── (auth)/
    │   │   └── login/
    │   │       └── page.tsx
    │   ├── (dashboard)/        # layout compartilhado (sidebar + header)
    │   │   ├── layout.tsx
    │   │   ├── cadastro/page.tsx
    │   │   ├── produtos/page.tsx
    │   │   ├── parceiros/page.tsx
    │   │   ├── inbound/page.tsx
    │   │   ├── outbound/page.tsx
    │   │   ├── inventario/page.tsx
    │   │   ├── matriz-fisica/page.tsx
    │   │   ├── etiquetas/page.tsx
    │   │   ├── fiscal/page.tsx
    │   │   ├── manutencao/page.tsx
    │   │   ├── requisicao/page.tsx
    │   │   ├── auditoria/page.tsx
    │   │   ├── torre-controle/page.tsx
    │   │   ├── relatorios/page.tsx
    │   │   └── configuracoes/page.tsx
    │   ├── middleware.ts         # proteção de rotas via JWT
    │   └── layout.tsx            # root layout (providers: query, theme)
    │
    ├── components/
    │   ├── ui/                  # shadcn/ui (copiados, sem dependência de versão)
    │   ├── layout/              # Sidebar, Header, PageHeader
    │   ├── data-table/          # TanStack Table wrapper reutilizável
    │   ├── charts/              # wrappers Recharts
    │   └── forms/               # formulários compostos reutilizáveis
    │
    ├── hooks/
    │   ├── useAuth.ts
    │   ├── useEstoque.ts
    │   └── ...
    │
    ├── lib/
    │   ├── api.ts               # cliente fetch tipado (gerado por openapi-typescript)
    │   ├── auth.ts              # helpers JWT (decode, validade, refresh)
    │   └── utils.ts
    │
    ├── types/                   # tipos gerados + tipos manuais adicionais
    │   └── api.d.ts             # auto-gerado: npx openapi-typescript http://localhost:8000/openapi.json
    │
    ├── tailwind.config.ts
    ├── next.config.ts
    ├── package.json
    └── tsconfig.json
```

---

## 6. Autenticação

### Fluxo
1. Usuário envia credenciais → FastAPI `/api/v1/auth/login` → retorna `access_token` (JWT)
2. Next.js armazena o token em **`httpOnly` cookie** via API Route própria (`/api/auth/session`)
3. `middleware.ts` do Next.js lê o cookie em toda requisição de rota protegida — sem acesso via JavaScript (proteção contra XSS)
4. Requests ao FastAPI: Next.js injeta o token no header `Authorization: Bearer <token>` server-side

### Timeout de Inatividade
Mantém a lógica atual de 10 minutos. No Next.js:
- `zustand` armazena `lastActivity` atualizado em cada interação
- `useEffect` global no root layout verifica e limpa a sessão

### Refresh Token (melhoria futura)
Adicionar endpoint `/api/v1/auth/refresh` no FastAPI para emitir novos tokens sem re-login. Recomendado para sessões enterprise > 8h.

---

## 7. Theming (a solução real)

`next-themes` injeta `data-theme="dark"|"light"` no `<html>`. Tailwind usa `class` strategy. shadcn/ui usa CSS custom properties mapeadas para o tema:

```css
:root {
  --background: 0 0% 100%;
  --foreground: 222.2 84% 4.9%;
  --primary: 221.2 83.2% 53.3%;
}
.dark {
  --background: 222.2 84% 4.9%;
  --foreground: 210 40% 98%;
}
```

**Resultado:** grids, inputs, botões, modais, gráficos — tudo consome as mesmas variáveis. Toggle em runtime funciona 100% sem recarregar a página. Este é o padrão correto.

---

## 8. Grids de Dados

TanStack Table v8 é headless: fornece lógica (sort, filter, pagination, row selection), você fornece o HTML e CSS. Exemplo do padrão adotado:

```tsx
// components/data-table/DataTable.tsx
export function DataTable<TData>({ columns, data }: DataTableProps<TData>) {
  const table = useReactTable({ data, columns, getCoreRowModel: getCoreRowModel() })

  return (
    <div className="rounded-md border border-border">
      <Table>
        <TableHeader>
          {table.getHeaderGroups().map(headerGroup => (
            <TableRow key={headerGroup.id}>
              {headerGroup.headers.map(header => (
                <TableHead key={header.id} className="text-foreground font-medium">
                  {flexRender(header.column.columnDef.header, header.getContext())}
                </TableHead>
              ))}
            </TableRow>
          ))}
        </TableHeader>
        <TableBody>
          {table.getRowModel().rows.map(row => (
            <TableRow key={row.id} className="hover:bg-muted/50">
              {row.getVisibleCells().map(cell => (
                <TableCell key={cell.id} className="text-foreground">
                  {flexRender(cell.column.columnDef.cell, cell.getContext())}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}
```

`text-foreground` e `bg-muted` são Tailwind tokens que apontam para as CSS variables do tema. O grid responde ao dark/light toggle automaticamente.

---

## 9. Geração de Tipos da API (Zero Drift)

```bash
# Executa uma vez por release ou quando a API muda
npx openapi-typescript http://localhost:8000/openapi.json --output frontend/types/api.d.ts
```

A partir disso, todos os hooks de dados são tipados:

```typescript
// hooks/useEstoque.ts
import { createClient } from 'openapi-fetch'
import type { paths } from '../types/api'

const client = createClient<paths>({ baseUrl: process.env.NEXT_PUBLIC_API_URL })

export function useEstoque() {
  return useQuery({
    queryKey: ['estoque'],
    queryFn: async () => {
      const { data, error } = await client.GET('/api/v1/estoque')
      if (error) throw error
      return data  // totalmente tipado — IntelliSense completo
    }
  })
}
```

Benefício: qualquer mudança no backend (novo campo, endpoint renomeado) quebra o TypeScript em compile time — não em produção.

---

## 10. Infraestrutura e Deploy

### Docker Compose Atualizado

```yaml
services:
  tracebox_db:
    image: postgres:16-alpine
    # ... configuração atual

  tracebox_api:
    build: .
    # ... configuração atual
    environment:
      - ALLOWED_ORIGINS=http://tracebox_web:3000,https://tracebox.empresa.com

  tracebox_web:                  # NOVO
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_API_URL=http://tracebox_api:8000
    depends_on:
      - tracebox_api

  nginx:                         # NOVO — reverse proxy
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./certs:/etc/nginx/certs
    depends_on:
      - tracebox_web
      - tracebox_api
```

### Dockerfile do Frontend

```dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json .
RUN npm ci
COPY . .
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
EXPOSE 3000
CMD ["node", "server.js"]
```

`output: 'standalone'` no `next.config.ts` gera um binário autocontido — sem `node_modules` no container de produção.

---

## 11. Estratégia de Migração (Faseada)

### Fase 0 — Preparação Backend (1–2 semanas)
- [ ] Adicionar e configurar CORS no FastAPI (`CORSMiddleware` com `allowed_origins` por variável de ambiente)
- [ ] Auditar todos os endpoints: documentar parâmetros, respostas, códigos de erro
- [ ] Adicionar endpoint de refresh token (`/api/v1/auth/refresh`)
- [ ] Validar que `/openapi.json` está completo e correto
- [ ] Setup projeto Next.js base (estrutura de pastas, Tailwind, shadcn/ui, TanStack Query)
- [ ] Configurar CI pipeline (build, lint, type-check)

### Fase 1 — Shell e Autenticação (1 semana)
- [ ] Tela de login com validação Zod + React Hook Form
- [ ] `middleware.ts` protegendo rotas
- [ ] Layout base: sidebar com navegação, header com user info e toggle de tema
- [ ] Dark/light theme 100% funcional
- [ ] Deploy de validação (ambiente dev)

### Fase 2 — Módulos de Cadastro (2–3 semanas)
- [ ] Parceiros (CRUD completo)
- [ ] Produtos / Catálogo
- [ ] Cadastro geral
- [ ] Emitente e Configurações fiscais

### Fase 3 — Módulos Operacionais (3–4 semanas)
- [ ] Inbound (recebimento)
- [ ] Outbound (expedição)
- [ ] Inventário e Matriz Física
- [ ] Etiquetas (QR Code, impressão)

### Fase 4 — Módulos Especializados (2–3 semanas)
- [ ] Fiscal: NF-e 55, Remessa/Retorno Conserto
- [ ] DANFE: download PDF gerado pelo backend
- [ ] Manutenção e Requisições
- [ ] Auditoria e Compliance

### Fase 5 — Torre de Controle e Relatórios (1–2 semanas)
- [ ] Dashboards (Recharts)
- [ ] Relatórios (download PDF/Excel)
- [ ] KPIs e métricas em tempo real

### Fase 6 — Testes, Hardening e Go-Live (1–2 semanas)
- [ ] Testes E2E com Playwright (fluxos críticos)
- [ ] Testes de carga nos endpoints
- [ ] Revisão de segurança (headers, CORS, cookies)
- [ ] Go-live com Streamlit em paralelo por 2 semanas
- [ ] Descomissionamento do Streamlit

**Timeline total estimado:** 12–16 semanas com um desenvolvedor dedicado ao frontend.

---

## 12. Riscos e Mitigações

| Risco | Probabilidade | Impacto | Mitigação |
|-------|--------------|---------|-----------|
| API inconsistências descobertas durante migração | Alta | Médio | Fase 0 de auditoria + OpenAPI types quebram em compile time |
| Curva de aprendizado React/TypeScript | Média | Alto | shadcn/ui é copy-paste; documentação extensa; começar por módulos simples |
| Regressões no backend durante migração | Baixa | Alto | Manter suite de testes FastAPI; Streamlit em paralelo como fallback |
| Dados sensíveis (NF-e, fiscal) expostos | Baixa | Crítico | httpOnly cookies; HTTPS obrigatório; sem token em localStorage |
| Prazo estourado | Alta | Médio | Priorizar módulos por volume de uso; Streamlit não sai do ar até validação total |

---

## 13. O que NÃO muda

- FastAPI: nenhum endpoint precisa ser reescrito
- Banco de dados: schema, migrations, dados — intactos
- Lógica de negócio: services, repositories — intactos
- Deploy de banco: container PostgreSQL — mantido
- Geração de PDF (DANFE): reportlab no backend — mantido
- Integração com SEFAZ/NF-e: mantida no backend

A migração é uma **troca de camada de apresentação**, não uma reescrita do sistema.

---

## 14. Resultado Esperado

| Aspecto | Streamlit (atual) | Next.js (destino) |
|---------|-------------------|-------------------|
| Tema dark/light | Parcial (grids não respondem) | 100% — todas as superfícies |
| Performance | Re-render de página completa | Client-side routing, sem reload |
| Grids | Canvas (CSS não penetra) | HTML puro, totalmente temável |
| UX | "Dashboard interno" | Enterprise-grade |
| Testes de UI | Inexistente | Playwright + Vitest |
| Escalabilidade de time | 1 desenvolvedor Python | Qualquer dev React/TS |
| Mobile/Responsividade | Limitada | Nativa (Tailwind responsive) |
| Time to interact (TTI) | 2–4s (server render completo) | < 1s (client navigation) |

---

*Documento gerado para revisão e aprovação antes do início da Fase 0.*
