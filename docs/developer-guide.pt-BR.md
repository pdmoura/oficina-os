# Guia do desenvolvedor

[![English](https://img.shields.io/badge/lang-English-1f6feb.svg)](developer-guide.md)
[![Português](https://img.shields.io/badge/lang-Portugu%C3%AAs-2ea043.svg)](developer-guide.pt-BR.md)

Como o Oficina OS é construído, testado, traduzido, implantado e operado. Para usar o sistema, veja o
[manual do usuário](user-manual.pt-BR.md).

## Sumário

1. [Visão geral](#1-visão-geral)
2. [Estrutura do repositório](#2-estrutura-do-repositório)
3. [Modelo de dados](#3-modelo-de-dados)
4. [Segurança](#4-segurança)
5. [Interface](#5-interface)
6. [Páginas públicas e rotas](#6-páginas-públicas-e-rotas)
7. [Relatórios](#7-relatórios)
8. [NFS-e](#8-nfs-e)
9. [Traduções](#9-traduções)
10. [Desenvolvimento local e testes](#10-desenvolvimento-local-e-testes)
11. [Ambientes e implantação](#11-ambientes-e-implantação)
12. [Operação](#12-operação)
13. [Convenções](#13-convenções)
14. [Personalização para um cliente](#14-personalização-para-um-cliente)
15. [Problemas comuns](#15-problemas-comuns)

## 1. Visão geral

O Oficina OS são três módulos do Odoo 19 Community, sob a licença OPL-1:

| Módulo | Depende de | Papel |
|---|---|---|
| `workshop_os` | `base`, `web`, `mail`, `mail_bot`, `auth_signup` | Veículos, OS, situações, checklists, fotos, o app do mecânico, a página de aprovação do cliente, o painel do escritório, o fechamento mensal, PDFs, a marca da oficina, o guia do sistema. |
| `l10n_br_nfse_nacional` | `base`, `mail`, `certificate` | NFS-e pelo Sistema Nacional: modos assistido e direto, validação por XSD, XMLDSig, mTLS, cancelamento, DANFSe. Funciona sem o módulo da oficina. |
| `workshop_os_nfse` | os dois acima | Ligação, instalada sozinha: a nota de uma OS ou de um fechamento mensal. |

Os textos-fonte são em inglês; a tradução que acompanha é `pt_BR`. Tudo o que é de uma oficina específica (nome,
logos, cores, textos, serviços, usuários) é dado, não código: um mesmo código atende qualquer número de oficinas.

## 2. Estrutura do repositório

```
workshop_os/
  controllers/        workshop_os.py (página pública, imagens da marca), web.py (manifesto do app instalável)
  models/             um arquivo por modelo; res_company.py guarda as funções de marca e tema
  wizard/             workshop.order.print (a pergunta "Incluir fotos")
  views/              <modelo>_views.xml, workshop_os_menus.xml, templates públicos e do web client
  report/             <relatório>_reports.xml (ações) e _templates.xml (QWeb)
  security/           grupos, ir.model.access.csv, regras por modelo
  data/               situações, localizações, setores, checklists, sequência, asset do tema (inglês, traduzido)
  demo/               empresa, usuários e OS de demonstração
  static/src/
    app/              app do mecânico (client action em OWL): mechanic_app.*, screens.js, utils.js
    backend/          painel, widgets de campo, ajustes de telas (abas, botões, salvar), link do cliente
    tour/             guia do sistema (serviço, sobreposição, passos)
    public/           página de aprovação do cliente
    scss/tokens.scss  tokens de design do app, do painel e da página pública
  i18n/pt_BR.po       tradução do módulo; i18n_extra/pt_BR.po completa lacunas do pt_BR do próprio Odoo
  migrations/<versão>/ scripts pre-/post-migrate
  tests/
l10n_br_nfse_nacional/  models/, tools/nfse_xml.py (XML, assinatura, regras de texto), wizard/ (cancelamento), data/xsd, report/
workshop_os_nfse/       models/ (mixin workshop.nfse.source, extensões), views/, tests/
deploy/                 entrypoint.sh, docker-compose.yml, placeholder.py, sample_data.py
Dockerfile, docker-compose.yml (local), render.yaml (demo), .github/workflows (CI, keep-alive)
docs/                   manuais, roteiros, imagens
```

## 3. Modelo de dados

| Modelo | O que é | Observações |
|---|---|---|
| `workshop.vehicle` | Um caminhão, pela placa | Placa normalizada (Mercosul e antiga) e única por empresa; OS aberta e histórico calculados. |
| `workshop.order` | Uma OS | Número da sequência `workshop.order` ao criar ("Novo" até lá). `state`: rascunho → aprovada → pronta → entregue (e recusada, cancelada). `stage_id` é a posição no pátio, independente do `state`. `access_token` público e `public_url` calculado. |
| `workshop.order.line` | Um serviço ou peça da OS | `approval` pendente/aprovado/recusado; `is_part` (copiado do catálogo) divide a OS em `amount_services` e `amount_parts`; `_service_rows(parts=False)` e `_invoice_description()` montam o detalhamento usado pelo relatório do fechamento e pela NFS-e, sem as peças na nota. |
| `workshop.order.photo` | Uma foto | `kind` entrada/serviço/saída; guardada como anexo ou no Cloudinary (URL); `show_to_customer`. |
| `workshop.order.checklist` | Uma resposta do checklist | Copiada de um modelo (`load_checklist`). |
| `workshop.order.stage.log` | Tempo em cada situação | Gravado a cada troca de situação; situações de espera não contam como trabalho. |
| `workshop.stage`, `.location`, `.sector`, `.service` | Cadastros da oficina | Dados iniciais em `data/`, em inglês com tradução pt_BR. |
| `workshop.checklist.template(.item)` | Modelos de checklist | Os itens têm xml id, então cada um é traduzível. |
| `workshop.billing` | Fechamento mensal por cliente | rascunho → confirmado → faturado → pago; prende as suas OS. |
| `workshop.order.print` | Transitório | Janela de impressão; passa `workshop_without_photos` no contexto do relatório. |
| `res.company` | Marca e textos | Cores de destaque e fundo, logos, ícone, imagem de link, garantia e termos; `_workshop_theme_scss()` gera o tema. |
| `res.users.settings` | Estado da interface por usuário | `workshop_theme`, `workshop_tour_office_done`, `workshop_tour_app_done`. |
| `res.partner` | Cliente | `workshop_customer`, `workshop_auto_approve` (frotas com contrato). |
| `l10n_br_nfse_nacional.document` | Uma NFS-e | rascunho → emitida / erro → cancelada; XML da DPS e da NFS-e anexados; `workshop_order_id` / `workshop_billing_id` do módulo de ligação, com uma nota ativa por origem (restrição). |

Fotos, PDFs e todos os anexos ficam **no PostgreSQL** nas imagens implantadas (`ir_attachment.location = db`):
um dump do banco é um backup completo.

## 4. Segurança

- **Grupos:** `workshop_os.workshop_os_group_user` (Mecânico) e `workshop_os.workshop_os_group_manager`
  (Escritório, que inclui Mecânico e `base.group_partner_manager`). A NFS-e tem grupo próprio, dado ao Escritório
  pelo módulo de ligação.
- **Regras de registro:** todo modelo é restrito às empresas do usuário (`<modelo>_rule_company`).
- **Os passos do escritório são garantidos no modelo**, não só escondidos na tela: aprovar, recusar, cancelar,
  reabrir, os campos da aprovação e remover linhas aprovadas passam por `workshop.order._check_office()` em
  `create`/`write`/`unlink`. Todo método público pode ser chamado por RPC, por isso isso importa. Duas exceções
  estreitas rodam como superusuário depois das próprias verificações: `action_undo_done()` (o mecânico volta uma OS
  pronta para a situação que ela tinha, até ser entregue, faturada ou ter nota: `_check_can_undo_done()`) e
  `_app_create_partner()` (cliente cadastrado no portão, só com nome, telefone e tipo, já que mecânico não cria
  contatos). O app também edita e exclui OS (`app_edit`, `app_delete`) com as mesmas travas: a exclusão vale para OS
  abertas por engano, antes de alguém aprovar, e remove junto o caminhão ou o cliente cadastrados só para ela.
- **A resposta do cliente** vem por `/os/<token>/decision`, comparada em tempo constante, e roda o método privado
  `_customer_decide()`, que não pode ser chamado por RPC.
- **Fotos** só aceitam endereços do Odoo (`/web/image/`) ou de `https://res.cloudinary.com/`, e o anexo precisa ser
  da mesma OS. Os envios ao Cloudinary são assinados no servidor; o navegador só recebe uma assinatura de uso único
  (`upload_ticket`).
- **O auto-cadastro está fechado** e a apresentação do OdooBot, desligada.
- Segredos (senha do banco, senha do administrador, segredo do Cloudinary, certificado A1) ficam no ambiente ou no
  banco, nunca no repositório.

## 5. Interface

### App do mecânico

Uma client action em tela cheia (`workshop_os.mechanic_app`, caminho `/odoo/mechanic-app`) escrita em OWL. As
telas (`HomeScreen`, `NewOrderScreen`, `OrderScreen`) ficam numa pilha pequena, para o botão de voltar funcionar como
num app de celular. Cada tela carrega os dados numa só chamada a um método do modelo: `app_home`, `app_read`,
`app_new_form`, `app_create`, `app_add_services`, `app_action`, `app_save_checklist`, `upload_ticket` + `add_photo`,
`find_by_plate`. Serviços e clientes nunca vêm inteiros: o componente `SearchSelect` consulta `app_services` e
`app_partners` enquanto o mecânico digita.

Pode ser instalado como app (PWA): `controllers/web.py` dá ao manifesto o nome da oficina e o inicia em `/odoo`, que
leva cada perfil à sua tela (`_workshop_home_action`). O celular guarda a OS digitada pela metade no `localStorage`.

Observação de OWL: um handler em arrow function no template (`t-on-click="() => abrir(x)"`) chama o método sem
`this`; componentes que usam isso rodam `bindMethods(this)` no `setup()` (há um teste que confere).

### Escritório

- **Painel:** client action `workshop_os.dashboard`, dados de `workshop.order.dashboard_data()`.
- **Ajustes de telas** (`static/src/backend/`):
  - `notebook.xml`: no celular, abas com mais de duas páginas viram um `<select>`;
  - `status_bar_buttons.xml`: no celular, os dois primeiros botões do cabeçalho ficam à mostra;
  - `form_status_indicator.xml`: botões Salvar/Descartar com texto (uma barra embaixo no celular);
  - `customer_link.js`: widget do cabeçalho que copia o link de aprovação no próprio toque;
  - `backend.scss`: alinhamento da barra de título, cartões no celular, visual do seletor de seções.
  - Views `<kanban>` dentro de campos one2many dão cartões no celular em vez de tabelas cortadas.
- **As extensões de templates são testadas:** `test_template_extensions_find_their_place` confere cada xpath das
  nossas extensões contra os templates do próprio Odoo, para que uma atualização do Odoo que mova um ponto de
  encaixe falhe no CI em vez de quebrar todos os formulários.

### Marca e tema

As cores de destaque e de fundo de `res.company` viram variáveis SCSS (`_workshop_theme_scss`), gravadas num anexo
servido em `/_custom/workshop_os/brand_variables.scss` e colocadas antes de `web._assets_primary_variables` por um
`ir.asset`. Salvar a marca reescreve o arquivo e limpa o cache de assets, e os botões, links e a barra do próprio
Odoo passam a usar as cores da oficina. Texto sobre branco usa o destaque escurecido até passar no WCAG AA
(`$primary`); superfícies preenchidas usam o destaque puro (`$o-brand-primary`).

### Guia do sistema

`static/src/tour/workshop_tour.js` registra o serviço `workshop_tour`, uma sobreposição em `main_components` e um
item no menu do usuário. Os dois roteiros, `office` e `app`, são listas de passos:

```js
{
    page: "workshop.order#form",          // tag da client action, modelo ou "modelo#form"
    target: ".o_form_view .o_form_statusbar",  // o que destacar; sem alvo, o cartão fica centralizado
    open: () => action.doAction(...),     // abre a tela quando outra está aberta
    when: async () => true,               // deixa o passo de fora (sem OS ainda, sem permissão...)
    optional: true,                       // pula se o alvo não aparecer
    title: _t("..."), body: _t("..."),
}
```

Cada roteiro abre sozinho na primeira visita do usuário (painel ou tela inicial do app) e se marca como visto em
`res.users.settings`. Para acrescentar um passo, inclua-o em `officeSteps()` ou `appSteps()`, traduza os textos e
percorra o guia em 390 px e 1280 px.

## 6. Páginas públicas e rotas

| Rota | Acesso | O que é |
|---|---|---|
| `/os/<token>` | público | Página de aprovação (situação, histórico, fotos por momento, serviços com caixa de seleção, assinatura). |
| `/os/<token>/decision` | público, JSON | A aprovação ou recusa do cliente. |
| `/workshop_os/app-icon/<tamanho>` | público | Ícone do app gerado a partir do símbolo da empresa. |
| `/workshop_os/favicon.ico`, `/workshop_os/icon/<tamanho>` | público | O ícone do navegador da empresa, cada tamanho como foi desenhado. |
| `/workshop_os/og-image/<company_id>` | público | Imagem de pré-visualização de links. |
| `/workshop_os/logo/<company_id>/<variante>` | público | Logos (dark, light, mark, mark_light). |
| `/web/manifest.webmanifest` | público | Manifesto do app instalável com o nome e as cores da oficina. |

## 7. Relatórios

- **OS** (`workshop_os.report_workshop_order`): `web.basic_layout` com a marca da oficina, serviços, totais, fotos
  por momento (até oito, embutidas quando estão no banco), garantia e assinaturas. `action_print()` pergunta pelas
  fotos quando há alguma e imprime com `config=False`, porque o relatório não usa o layout externo do Odoo.
- **Fechamento mensal** (`workshop_os.report_workshop_billing`): o detalhamento de `_service_rows()`, as peças
  (`_service_rows(parts=True)`) e as OS.
- **DANFSe** (`l10n_br_nfse_nacional`): desenhado a partir do XML autorizado, conforme a NT 008, com o QR code da
  consulta pública.

## 8. NFS-e

- **Modo assistido:** os campos calculados `assist_*` organizam cada valor para o site do Emissor Nacional; o
  usuário cola de volta a chave de acesso e `action_register_issued()` registra a nota.
- **Modo direto:** a DPS é montada pelas regras do leiaute nacional, validada contra os XSDs em `data/`, assinada
  (XMLDSig envelopada, RSA-SHA1, C14N inclusiva) com o certificado A1 guardado pelo módulo `certificate` do Odoo,
  enviada por TLS mútuo, e a resposta é lida sem diferenciar maiúsculas. Uma resposta perdida que volta como E0014
  recupera a nota que já existe.
- **Texto:** `tools/nfse_xml.clean_text()` mantém a faixa Latin-1 que o schema aceita; a descrição tem no máximo
  `MAX_DESCRIPTION` (1000) caracteres.
- **Dados do cliente:** `res.partner` se preenche pelo CNPJ (`_onchange_vat_fill_from_cnpj`: BrasilAPI e, se ela não
  responder, Minha Receita, as duas cópias gratuitas do cadastro da Receita Federal; só o CNPJ é enviado) e pelo CEP
  (`_onchange_zip_fill_address`, ViaCEP). O onchange do CNPJ preenche o CEP, e o encadeamento de onchanges do Odoo
  roda então o do CEP, que traz os nomes com acento. `cnpj_is_valid()` confere os dígitos de CNPJ numérico e
  alfanumérico (formato de julho de 2026) antes de qualquer consulta. O módulo depende de `partner_autocomplete` só
  para tirar, em `_get_view`, o componente pago dele do campo `vat`; o nome continua com ele.
- **Ligação:** `workshop.nfse.source` dá às OS e aos fechamentos `action_create_nfse()` (reaproveita a nota ativa) e
  `_nfse_values()`. O valor da nota é `_nfse_amount()`, só os serviços (peça é faturada como mercadoria), e uma
  origem sem serviços não cria nota. Uma nota feita à mão pode escolher uma OS ou um fechamento e é preenchida por
  onchange; uma restrição mantém uma nota ativa por origem.

## 9. Traduções

1. Escreva todo texto em inglês: no código com `_()` / `self.env._()` (Python) ou `_t()` (JS), no XML como texto.
2. Atualize o módulo num banco com pt_BR carregado e exporte:
   `odoo i18n export -c <conf> -d <banco> -l pt_BR -o /tmp/workshop_os.po workshop_os`
3. Junte a exportação ao `i18n/pt_BR.po`, mantendo as traduções existentes e acrescentando as novas. Mantenha cada
   frase numa linha só no XML: uma quebra de linha dentro da frase vai parar dentro do msgid.
4. Traduções de código Python são lidas do `.po` em tempo de execução (reinicie o Odoo); as de telas e campos são
   carregadas no banco na atualização. Uma tradução existente não é sobrescrita na atualização: quando o texto-fonte
   muda, confira o valor no banco (ou atualize com `--i18n-overwrite` num banco de teste).
5. `i18n_extra/pt_BR.po` traz uns 140 termos que o próprio Odoo entrega sem tradução em pt_BR ("My Preferences" e
   outros); o web client busca a tradução em qualquer módulo.

## 10. Desenvolvimento local e testes

```bash
docker compose up -d db
docker compose run --rm odoo odoo -d oficina -i workshop_os,workshop_os_nfse --with-demo --load-language=pt_BR --stop-after-init
docker compose up -d odoo          # http://localhost:8070
```

Os módulos são montados a partir da pasta de trabalho. Mudanças em Python pedem `docker compose restart odoo`;
em XML e dados, uma atualização (`-u workshop_os`); em SCSS/JS, um reinício.

Testes (88 no total):

```bash
docker compose run --rm odoo odoo -d test -i workshop_os,workshop_os_nfse \
  --test-tags /workshop_os,/l10n_br_nfse_nacional,/workshop_os_nfse --stop-after-init
```

Cobrem placas, o fluxo da OS e os passos do escritório por RPC, fotos, a página do cliente, o fechamento mensal,
relatórios, a DPS da NFS-e contra os XSDs, assinaturas, a API simulada, cancelamento, DANFSe, uma nota ativa por
origem, descrições de nota, tema e compilação de estilos, extensões de templates, tradução de termos do Odoo, o
manifesto e as preferências do guia.

**CI** (`.github/workflows/ci.yml`, a cada push e pull request): instalação e testes, instalação com dados de
demonstração em português, a imagem de produção e o conjunto auto-hospedado com PostgreSQL próprio (entra como o
usuário de escritório da demonstração).

## 11. Ambientes e implantação

```
 desenvolvedor ── git push ──▶ GitHub (main) ──▶ CI
                                 │
                                 ├──▶ Render (autoDeploy) ──▶ demonstração pública, dados de exemplo
                                 │
                                 └──▶ servidor de produção: implantado de propósito (git pull + docker compose)
```

- **GitHub** guarda o código. Nada secreto é versionado; `deploy/.env` fica fora.
- **A demonstração** é um serviço web no Render construído pelo `Dockerfile` (`render.yaml`), com
  `autoDeploy: true`: cada push na `main` a reconstrói. Roda num PostgreSQL gerenciado com `LOAD_DEMO=true`.
- **Um servidor de produção** roda `deploy/docker-compose.yml` a partir de um clone do repositório. Ele **não** é
  atualizado por um push: alguém implanta de propósito, e o sistema de uma oficina só muda quando se quer.

### A imagem e o entrypoint

O `Dockerfile` copia os três módulos para a imagem oficial do Odoo 19. O `deploy/entrypoint.sh` configura o Odoo a
partir de variáveis de ambiente e, ao iniciar:

- **banco vazio:** cria o banco, guarda os anexos no banco, instala os módulos em pt_BR (com dados de exemplo quando
  `LOAD_DEMO=true`) e cria o administrador;
- **banco existente:** compara uma impressão digital dos módulos com a salva em `ir_config_parameter`
  (`deploy.addons_fingerprint`) e roda `-u` nos módulos só quando o código mudou.

Durante a instalação ou atualização, o `deploy/placeholder.py` responde na porta com uma página "preparando o
sistema".

### Implantar num servidor de produção

```bash
ssh <servidor>
cd /opt/oficina-os
sudo docker exec oficina-os-backup-1 sh -c 'pg_dump -Fc "$DB_NAME" > /backups/pre-deploy-$(date +%Y%m%d-%H%M).dump'
git pull --ff-only
sudo docker compose -f deploy/docker-compose.yml --env-file deploy/.env up -d --build odoo
sudo docker logs -f oficina-os-odoo-1      # "[deploy] new release: upgrading ..." e depois "Modules loaded"
```

### Migrações

- A atualização de um módulo roda os scripts pre-, post- e end-migrate de `migrations/<versão>/` só quando a versão do
  manifesto aumenta. Aumente `version` sempre que acrescentar uma migração, e faça scripts que possam rodar de novo.
- As migrações existentes renomeiam xml ids (seguindo as diretrizes do Odoo), renomeiam o modelo da NFS-e com a
  tabela e todas as referências, e transformam dados iniciais em português não editados em textos-fonte em inglês
  com tradução.
- Um modelo removido deixa a tabela para trás (o Odoo só remove a linha de `ir.model` depois de todas as etapas de
  migração); apague-a numa versão seguinte, conferindo o registry.

## 12. Operação

- **Backups:** o serviço `backup` do `deploy/docker-compose.yml` grava um `pg_dump` comprimido em
  `deploy/backups/<banco>-<data>.dump` todo dia e guarda `BACKUP_DAYS` (14) dias. Faça um dump manual antes de cada
  implantação. Os anexos estão no banco, então o dump é completo. Copie os dumps também para fora do servidor.
- **Restaurar** (a oficina fica fora do ar por um minuto):

  ```bash
  sudo docker compose -f deploy/docker-compose.yml --env-file deploy/.env stop odoo
  sudo docker exec -i oficina-os-db-1 pg_restore -U odoo -d odoo --clean --if-exists < deploy/backups/<arquivo>.dump
  sudo docker compose -f deploy/docker-compose.yml --env-file deploy/.env start odoo
  ```

- **Voltar uma versão:** faça checkout do commit anterior e implante de novo. Quando a versão migrou dados, restaure
  o dump tirado antes dela.
- **Shell do Odoo:** `sudo docker exec -it oficina-os-odoo-1 odoo shell -c /tmp/odoo.conf -d odoo --no-http`.
- **Dados de exemplo** (`deploy/sample_data.py`), rodados num shell do Odoo:
  - `SAMPLE=create PHOTOS=<pasta>` cria clientes, caminhões e OS em todas as situações (marcados como
    `oficina_exemplo`) e um catálogo inicial de serviços;
  - `SAMPLE=check` lista o que a remoção apagaria;
  - `SAMPLE=remove` apaga os exemplos e o que foi feito em cima deles, reinicia a numeração das OS e para diante de
    uma NFS-e já emitida.
- **A demonstração** dorme no plano gratuito do Render; `.github/workflows/keepalive.yml` a acessa no horário da
  oficina quando a variável `KEEPALIVE_URL` do repositório está definida. O
  [demo-database.pt-BR.md](demo-database.pt-BR.md) explica como mudá-la para um banco novo.

## 13. Convenções

- **Diretrizes do Odoo:** xml ids `<modelo>_view_<tipo>`, `<modelo>_action`, `<modelo>_menu`,
  `<modelo>_rule_company`; nomes de view `<modelo>.view.<tipo>`; um arquivo por modelo; controllers em
  `<módulo>.py`; métodos na ordem computes → constraints → CRUD → ações → negócio → API do app; guardas
  `@api.ondelete` chamadas `_unlink_except_*`.
- **CSS:** classes com prefixo `o_workshop_*` (`o_workshop_app_*`, `o_workshop_dash_*`, `o_workshop_page_*`),
  classes de estado `o_workshop_is_*`, variáveis `--Workshop-*`; sem seletores de id. O compilador libsass calcula
  `min()` e `max()` do CSS por conta própria: evite-os com unidades misturadas.
- **Commits:** uma linha de resumo do que mudou para o usuário, depois o porquê. Testes e traduções vão junto com a
  mudança.

## 14. Personalização para um cliente

- **A marca é configuração:** nome, logos, cores, ícone, pré-visualização de link, textos, serviços, situações,
  checklists e usuários da oficina são dados, definidos nas Definições ou no banco. Uma oficina nova não precisa de
  código.
- **Código específico de um cliente** (uma integração, um relatório próprio, uma importação de dados) fica num módulo
  separado, por exemplo `<cliente>_custom`, num repositório privado, montado como pasta extra de módulos no servidor
  daquele cliente. Os módulos públicos continuam genéricos, e o código e os dados do cliente continuam privados.
- **Licença:** os módulos estão sob a Odoo Proprietary License (OPL-1). O código é público para leitura e
  avaliação; usar de verdade, adaptar para um cliente ou vender exige uma licença por escrito do autor (veja
  `COPYRIGHT`). O módulo privado de um cliente pode ter qualquer licença compatível com a OPL-1.

## 15. Problemas comuns

| Sintoma | Causa provável |
|---|---|
| Aviso "Erro de estilo" e o sistema com visual antigo | O SCSS não compilou (muitas vezes `min()`/`max()` com unidades misturadas); rode `test_styles_compile`. |
| Todo formulário com abas deixa de abrir (OwlError "cannot be located in element tree") | O xpath de uma extensão de template não encontra mais o template do Odoo; rode `test_template_extensions_find_their_place`. |
| Um texto novo aparece em inglês | Não está no `i18n/pt_BR.po`, ou o banco guardou uma tradução antiga; exporte, junte, atualize. |
| Depois de implantar, o sistema mostra "preparando o sistema" por minutos | A atualização está rodando; acompanhe o `docker logs`. Um erro ali deixa os dados da versão anterior intactos. |
| O teste de conexão do Cloudinary diz que a chave não existe | O campo da chave de API está com o nome da chave em vez do número. |
