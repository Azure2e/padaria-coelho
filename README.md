# Padaria Coelho — sistema completo

Site da padaria + cardápio + carrinho + PIX + WhatsApp + painel + API.

Valor de referência do pacote: **R$ 1.000**.

## Ligar tudo

No computador (precisa do Python 3):

```bash
cd padaria-aurora
python3 api/servidor.py
```

Ou:

```bash
./iniciar.sh
```

Abra:

- Site: http://127.0.0.1:8765/index.html
- Painel: http://127.0.0.1:8765/admin.html
- API: http://127.0.0.1:8765/api

Senha do painel e da API: **coelho1000**
Usuário da API: **admin**

## O que o sistema faz

- Vitrine Padaria Coelho (tema normal, claro e escuro)
- Som de notificação (Web Audio)
- Cardápio: pães, pastéis e bebidas
- Cesto de compras
- Pagamento PIX (QR + copia e cola), valor calculado no servidor
- Formulário e pedido via WhatsApp montados no backend
- Painel: pedidos, PIX, cardápio, preços e mensagens

## Trocar dados da loja

| O quê | Onde |
|---|---|
| WhatsApp | `api/whatsapp.py` → `NUMERO` |
| Chave PIX | `api/pagamentos.py` → `PIX_CHAVE` |
| Endereço e textos | `index.html` |
| Produtos | painel ou `api/produtos.json` |

## Rotas da API

Públicas: produtos, login, criar PIX, consultar PIX, WhatsApp contato/pedido.

Com login: cadastro de produto, atualizar preço, listar PIX, confirmar PIX, listar WhatsApp.

## Segurança inclusa

- Senha com PBKDF2 e token de 8 horas
- Preço do PIX calculado no servidor
- Nonce, rate limit, honeypot
- HMAC e log em `api/auditoria.jsonl`

## Pastas

```
padaria-aurora/
  index.html
  admin.html
  iniciar.sh
  css/  js/  img/
  api/servidor.py
```

Versão local (um computador). Para vários caixas, hospede o servidor e use a chave PIX e o WhatsApp reais.

## Estoque, entrega e relatório

- Estoque do dia no cardápio e no painel. Item some como esgotado.
- Entrega por bairro com taxa e pedido mínimo (`api/bairros.json`).
- Relatório de hoje no painel: PIX pago, entregas, WhatsApp e mais vendidos.
- Botão **Repor estoque do dia** volta a quantidade base.

## Rotação de logs

Padrão: 1 MB, 5 arquivos, gzip, também fecha o arquivo no dia seguinte.
Configura em `api/logs.json` ou no painel (Logs ao vivo).
`GET /api/logs/rotacao` · `POST /api/logs/rotacao` · `POST /api/logs/rotacionar`
