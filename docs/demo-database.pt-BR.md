# Novo banco para a demonstração

[![English](https://img.shields.io/badge/lang-English-1f6feb.svg)](demo-database.md)
[![Português](https://img.shields.io/badge/lang-Portugu%C3%AAs-2ea043.svg)](demo-database.pt-BR.md)

A demonstração pública roda no Render (serviço web gratuito), com o banco no Supabase (projeto gratuito).
Siga estes passos quando a demonstração precisar de um banco novo:

- uma conta ou um projeto novo no Supabase;
- um projeto excluído, ou pausado há tempo demais para restaurar;
- uma demonstração do zero.

O Supabase é só uma opção. Qualquer PostgreSQL 13+ serve: defina `DATABASE_URL` com a URL que o seu provedor entrega e pule os passos 1 e 2. Veja em [Banco](../README.pt-BR.md#banco-qualquer-postgresql-13-ou-mais-novo) o que o banco precisa permitir.

A parte do Odoo é automática. Na primeira subida, o contêiner cria o banco, instala os módulos em português
com dados de exemplo e define o administrador. Não há nada para rodar à mão no Odoo.

## 1. Criar o projeto no Supabase

1. **New project**, região **East US (North Virginia)**, a mesma do serviço no Render (Virginia). O Odoo faz
   muitas consultas por página, então o banco precisa ficar perto do serviço web.
2. Clique em **Generate a password** e guarde a senha no seu gerenciador de senhas. O Supabase não mostra
   ela de novo.
3. O plano gratuito permite dois projetos ativos por organização.

## 2. Copiar os dados de conexão

No projeto, abra **Connect → Direct → Session pooler** e anote:

| Campo | Exemplo |
|---|---|
| host | `aws-0-<region>.pooler.supabase.com` |
| port | `5432` |
| user | `postgres.<project-ref>` |

Use só o **session pooler**:

- a **conexão direta** é IPv6, e o Render não alcança;
- o **transaction pooler** quebra o `LISTEN` de que as tarefas agendadas do Odoo precisam.

## 3. Apontar o Render para ele

Em **Render → oficina-os → Environment**, defina estas variáveis e clique em **Save, rebuild, and deploy**:

| Variável | Valor |
|---|---|
| `DB_HOST` | host do pooler |
| `DB_PORT` | `5432` |
| `DB_USER` | `postgres.<project-ref>` |
| `DB_PASSWORD` | a senha do projeto |
| `DB_NAME` | `odoo` (qualquer nome; ele é criado na primeira subida) |
| `LOAD_DEMO` | `true` |
| `ODOO_ADMIN_EMAIL` | login do administrador |
| `ODOO_ADMIN_PASSWORD` | pelo menos 10 caracteres |

As variáveis do administrador só valem na primeira subida de cada banco. Para trocar o administrador depois,
faça isso dentro do Odoo.

**Numa conta nova do Render:** use **New → Blueprint** e escolha o repositório. O
[`render.yaml`](../render.yaml) cria o serviço e pede os mesmos segredos.

**Com o Render CLI pelo Git Bash no Windows:** comece o comando com `MSYS_NO_PATHCONV=1`. Sem isso, o Git
Bash transforma `/web/health` num caminho do Windows, e o deploy nunca passa na verificação de saúde.

## 4. Acompanhar a primeira subida

Leva de dois a três minutos. Em **Logs**, procure estas linhas:

```
[deploy] first boot: installing base
[deploy] installing workshop_os,workshop_os_nfse
HTTP service (werkzeug) running on ...:10000
```

Depois abra `https://<serviço>.onrender.com/web/health?db_server_status=1`. A resposta deve ser
`{"status": "pass", "db_server_status": true}`.

## 5. Logins da demonstração

| Login | Senha | Abre em |
|---|---|---|
| `escritorio` | `escritorio` | o painel do escritório |
| `mecanico` | `mecanico` | o app do mecânico (abra no celular) |

O administrador é o de `ODOO_ADMIN_EMAIL` e `ODOO_ADMIN_PASSWORD`. Não publique esse login.

## 6. Manter acordado

Defina a variável `KEEPALIVE_URL` do repositório com o endereço do serviço, por exemplo
`https://oficina-os.onrender.com`. Ela fica em **Settings → Secrets and variables → Actions → Variables**.

O [workflow de keep-alive](../.github/workflows/keepalive.yml) chama então a verificação de saúde com o teste
do banco. Ele roda a cada 10 minutos, das 07:00 às 21:00 (horário de Brasília), de segunda a sábado. Isso
evita tanto o sono do Render quanto a pausa do Supabase depois de uma semana sem atividade.

O GitHub desliga workflows agendados depois de 60 dias sem commits. Se a demonstração voltar a pausar,
reative o workflow em **Actions → Keep alive**.

## Recomeçar a demonstração sem apagar nada

Troque `DB_NAME` por um nome novo, por exemplo `demo_2026_10`, e faça o deploy. A primeira subida monta uma
demonstração nova nesse banco, e o antigo fica intacto. Quando tiver certeza de que não precisa mais do
banco antigo, apague-o no Supabase: o plano gratuito comporta 500 MB.

## Se o Supabase pausou o projeto

Abra o projeto no painel e clique em **Restore**. Projetos gratuitos pausados podem ser restaurados por 90
dias. Depois disso, recomece pelo passo 1.
