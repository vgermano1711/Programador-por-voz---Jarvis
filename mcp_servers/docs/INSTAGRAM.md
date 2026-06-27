# MCP Instagram — Documentação e Limitações Reais

## Situação atual (2024)

**Automação ampla do Instagram não é viável de forma segura.**

A Meta fecha regularmente contas que detectam comportamento automatizado
(scraping, like/follow bots, posting automatizado via terceiros).

## O que é e não é possível de forma segura

### NÃO é possível com segurança:
- Automatizar likes, comentários, follows via qualquer lib não-oficial
- Postar conteúdo via automação de conta pessoal (Instagrapi, Selenium + Instagram)
- Ler DMs via automação (a Meta detecta e suspende contas)
- Qualquer ação que simule comportamento humano na interface do app

### É possível com a API oficial (Meta Graph API):
- **Leitura de comentários** em posts da sua conta Business
- **Publicar posts** (imagem + legenda) em conta Business aprovada
- **Insights e métricas** da conta (alcance, impressões, engajamento)
- **Responder comentários** (via API de moderação)
- **Webhooks** para receber notificações de novos comentários/menções

## Implementação como servidor MCP (via Graph API)

### Pré-requisitos
1. Conta Instagram Business ou Creator (não funcional com conta pessoal)
2. Página do Facebook vinculada à conta Instagram
3. App aprovado no Meta for Developers com permissão `instagram_basic`,
   `instagram_content_publish`, `pages_read_engagement`
4. Access Token de longa duração (60 dias, renovável)

### Variáveis de ambiente necessárias (NUNCA hardcode)
```bash
export INSTAGRAM_ACCESS_TOKEN=seu_token_longa_duracao
export INSTAGRAM_ACCOUNT_ID=seu_id_de_conta_business
```

### Exemplo de servidor MCP mínimo (somente leitura)

```python
# mcp_servers/instagram_server.py (exemplo conceitual)
# Implementar como servidor MCP que expõe:
#   - get_recent_posts() → lista de posts com IDs
#   - get_comments(post_id) → comentários do post
#   - get_insights(post_id) → métricas de alcance
# 
# Para publicação (requer confirmação explícita):
#   - create_post(image_path, caption) → draft aguarda confirmação do usuário
```

### Configuração em config.yaml

```yaml
mcp:
  instagram:
    enabled: false
    mode: readonly              # "readonly" | "publish" (publish exige mais permissões)
    account_id_env: INSTAGRAM_ACCOUNT_ID
    token_env: INSTAGRAM_ACCESS_TOKEN
```

## Limitações documentadas

| Funcionalidade | Disponível | Observação |
|---|---|---|
| Ler posts próprios | Sim (API) | Apenas conta Business |
| Publicar posts | Sim (API) | Apenas conta Business, sem Reels via API |
| Ler DMs | Não | API não disponível para DMs pessoais |
| Automatizar likes | Não | Viola Termos de Serviço |
| Ler feed de outros | Não | Removido da API em 2018 |
| Stories | Parcial | Publicar sim, ler não |

## Recomendação para este projeto

Implementar apenas **leitura de comentários e métricas** via Graph API, 
com publicação como funcionalidade opcional que exige confirmação explícita
antes de cada post. Nunca automatizar interações (likes, follows, DMs).
