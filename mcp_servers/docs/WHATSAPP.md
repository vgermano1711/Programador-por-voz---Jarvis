# MCP WhatsApp — Documentação e Limitações Reais

## Situação atual (2024)

**Não existe servidor MCP oficial e seguro para WhatsApp.**

A Meta não oferece API do WhatsApp para uso pessoal/automação de conta pessoal.
A API oficial (Cloud API / Business API) existe apenas para contas Business
com aprovação formal da Meta, e não permite automação de chat pessoal.

## Abordagens disponíveis e seus riscos

### 1. Baileys / whatsapp-web.js (libs não-oficiais)

Funcionamento: fazem engenharia reversa do protocolo WhatsApp Web,
emulando um browser conectado à sua conta.

**Riscos documentados:**
- Banimento permanente da conta (Meta detecta automação e bane sem aviso)
- Vazamento de dados: bibliotecas de terceiros têm acesso total à conta
- Quebram sem aviso a cada atualização do WhatsApp Web
- Não têm garantia de manutenção ou segurança

**Se mesmo assim quiser implementar (APENAS em conta de TESTES):**

```bash
# Instale o servidor MCP customizado (exemplo conceitual)
npm install -g whatsapp-web.js

# Crie um servidor MCP mínimo que exponha send_message e get_messages
# Conecte SOMENTE a uma conta secundária criada para testes
# NUNCA conecte à conta principal
```

**Configuração de exemplo (NÃO ative em produção):**

```yaml
# config.yaml — seção mcp
mcp:
  whatsapp:
    enabled: false              # mantenha false por padrão
    test_account_only: true     # aviso semântico: não tem efeito técnico
    warn_before_send: true      # implementar confirmação explícita no código
```

**Regra de ouro:** qualquer mensagem WhatsApp enviada por voz DEVE passar por
confirmação explícita ("enviar mensagem para João dizendo olá — você confirma?")
antes de ser disparada. Nunca envio automático.

### 2. API Oficial Meta Business (única opção segura)

- Requer conta WhatsApp Business aprovada
- Requer cadastro no Meta for Developers
- Permite envio de templates aprovados (não chat livre)
- Custo por mensagem após tier gratuito

Implementação como MCP seria um servidor HTTP que wraps a Cloud API.
Essa é a única abordagem que não arrisca banimento.

## Recomendação

Para este projeto: **não implementar WhatsApp por ora.**
Foque em casos de uso que não dependem de plataformas com políticas restritivas.
Se integração for crítica, use a API Business oficial e documente o processo
de aprovação (pode levar dias a semanas).
