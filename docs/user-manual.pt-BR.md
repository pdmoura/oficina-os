# Manual do usuário

[![English](https://img.shields.io/badge/lang-English-1f6feb.svg)](user-manual.md)
[![Português](https://img.shields.io/badge/lang-Portugu%C3%AAs-2ea043.svg)](user-manual.pt-BR.md)

Este manual é para quem usa o sistema no dia a dia: o escritório, os mecânicos e quem configura a oficina.
Para instalar, manter ou alterar o sistema, veja o [guia do desenvolvedor](developer-guide.pt-BR.md).

## Sumário

1. [Quem faz o quê](#1-quem-faz-o-quê)
2. [Primeiro acesso](#2-primeiro-acesso)
3. [Painel](#3-painel)
4. [Ordens de serviço](#4-ordens-de-serviço)
5. [Aprovação pelo cliente](#5-aprovação-pelo-cliente)
6. [App do mecânico](#6-app-do-mecânico)
7. [Clientes e veículos](#7-clientes-e-veículos)
8. [Fechamento mensal](#8-fechamento-mensal)
9. [NFS-e](#9-nfs-e)
10. [Configurações](#10-configurações)
11. [Dúvidas frequentes](#11-dúvidas-frequentes)

## 1. Quem faz o quê

| Perfil | Onde trabalha | O que pode fazer |
|---|---|---|
| **Mecânico** | App do mecânico, no celular | Receber caminhões, mudar a situação e o box, lançar serviços, fotos e checklist, marcar o serviço como pronto. Não aprova orçamento nem mexe em preços e faturamento. |
| **Escritório** | Painel e telas do Odoo, no computador ou no celular | Tudo o que o mecânico faz, mais: aprovar ou recusar orçamentos, cancelar e reabrir OS, cadastrar clientes, fechar o mês e emitir NFS-e. |
| **Administrador** | Tudo, mais as Definições | Marca da oficina, textos, fotos, NFS-e, usuários. |

O perfil de cada pessoa é definido em **Definições → Usuários e empresas → Usuários**, no campo **Oficina**
(Mecânico ou Escritório).

## 2. Primeiro acesso

1. Abra o endereço do sistema no navegador e entre com o seu usuário e senha.
2. Cada perfil cai na sua tela: o escritório no **Painel**, o mecânico no **app do mecânico**.
3. Na primeira vez, um **guia** passa pelas telas principais, destacando cada parte com uma explicação.
   Use **Próximo** e **Voltar**, ou **Pular o guia**. Para abri-lo de novo:
   - no escritório: menu do seu usuário (canto superior direito) → **Guia do sistema**;
   - no app: menu (☰) → **Guia do sistema**.

### Instalar no celular

O sistema funciona como um aplicativo, sem loja:

- **Android (Chrome):** entre no sistema, toque em ⋮ → **Instalar app**.
- **iPhone (Safari):** entre no sistema, toque em Compartilhar (□↑) → **Adicionar à Tela de Início**.

Aparece um ícone com a marca da oficina. Ele abre em tela cheia e já vai direto para a tela do seu perfil.
O login fica salvo enquanto você usar o sistema pelo menos uma vez por semana.

## 3. Painel

A tela inicial do escritório (**Oficina → Painel**):

- **Números do dia:** caminhões na oficina, OS atrasadas, aguardando aprovação, prontas para retirada, o que foi
  concluído no mês e o que ainda não foi faturado. Tocar num número abre essas OS.
- **Situações:** um cartão por situação (Escritório, Aguardando peças, Na fila, Em serviço, Serviço parado,
  Teste / conferência) com a quantidade de caminhões. Tocar abre as OS daquela situação.
- **Listas:** OS em atraso, prontas para retirada e clientes do mês.
- **Botões no topo:** tema claro ou escuro, **App do mecânico** e **Todas as OS**.

O painel se atualiza sozinho a cada minuto.

## 4. Ordens de serviço

### O quadro

**Oficina → Ordens de serviço** mostra as OS abertas em colunas, uma por situação. No computador, arraste um
cartão para mudar a situação. No celular, deslize entre as colunas. O ícone de lista alterna para a visão em
tabela; há também calendário e análises.

Cada cartão mostra o número, a placa, o veículo, o cliente, o box, o tempo na situação atual e a data prometida
(em vermelho quando atrasada).

### Criar uma OS

O jeito mais rápido é pelo app do mecânico: **Receber veículo** (veja a seção 6), que parte da placa. No
escritório, use **Novo** no quadro: escolha o cliente e o veículo, a situação, o box, o mecânico e a previsão.
O número (OS 00001, OS 00002...) é dado ao salvar; até lá a OS aparece como "Novo".

### Dentro da OS

**Seções** (no celular, escolha a seção na lista amarela logo acima do conteúdo):

- **Serviços:** um por linha, com descrição, mecânico, quantidade, horas, preço e aprovação. Escolha no catálogo
  ou digite uma linha livre. Marque **Peça** nas peças e materiais: elas ganham a etiqueta PEÇA, e abaixo das linhas
  a OS mostra **Mão de obra** e **Peças** separadas. Peças ficam fora da NFS-e (seção 9).
- **Problema e diagnóstico:** o que o motorista relatou, o que o mecânico encontrou, notas internas e o texto de
  garantia.
- **Checklist:** o checklist de entrada respondido no app (OK, Atenção, Com defeito, N/A).
- **Fotos:** as fotos tiradas no app, separadas em **Entrada**, **Serviço** e **Saída**.
- **Histórico:** por onde a OS passou, quando e quanto tempo ficou em cada situação.
- **Aprovação:** quem aprovou, quando e a assinatura.

**Botões do topo** (no celular, os dois primeiros ficam à mostra e os demais no ⋮):

| Botão | Quando aparece | O que faz |
|---|---|---|
| **Aprovar** | aguardando aprovação ou recusada | Aprova o orçamento (os serviços pendentes ficam aprovados). |
| **Recusar** | aguardando aprovação | Marca o orçamento como recusado. |
| **Marcar como pronta** | aprovada | O serviço acabou; a OS vai para "Pronta para retirada". |
| **Entregar** | pronta | O caminhão saiu. |
| **WhatsApp** | OS aberta | Abre o WhatsApp com a mensagem e o link de aprovação para o telefone do cliente. |
| **Link do cliente** | sempre | Copia o link de aprovação e avisa "Link do cliente copiado". |
| **Imprimir** | sempre | Gera o PDF da OS. Se houver fotos, pergunta se elas entram (**Incluir fotos**). |
| **Reabrir** | pronta, entregue ou cancelada | Volta a OS para aprovada. |
| **Cancelar** | OS não entregue | Cancela a OS (pede confirmação). |

Aprovar, recusar, cancelar e reabrir são do escritório: o mecânico não vê esses botões e o sistema também recusa
se ele tentar por outro caminho. Uma OS já incluída num fechamento mensal não pode ser cancelada nem reaberta.

## 5. Aprovação pelo cliente

O **link do cliente** abre uma página sem login, com a marca da oficina:

- situação e histórico da OS;
- o problema relatado e o diagnóstico;
- as fotos marcadas para o cliente, separadas em Entrada, Serviço e Saída;
- os serviços, cada um com a sua caixa de seleção.

O cliente pode aprovar tudo ou só uma parte, digita o nome e assina com o dedo. A aprovação aparece no escritório
na hora. Quem prefere pode aprovar por telefone: o escritório usa **Aprovar** na OS.

**Frotas com contrato** (opção no cadastro do cliente) têm as OS aprovadas automaticamente.

## 6. App do mecânico

### Tela inicial

- **Busca:** digite parte da placa, o número da OS ou o cliente.
- **Números:** OS abertas, em atraso e aguardando aprovação.
- **Situações:** filtre os caminhões por situação. O botão ao lado alterna entre fileira e grade, e o app lembra a
  sua escolha.
- **Cartões:** cada caminhão no pátio, com placa, veículo, cliente, situação, tempo na situação, box e a etiqueta
  **Em atraso** quando passou da previsão.
- **Receber veículo** (botão amarelo): começa uma OS nova.

### Receber um caminhão

1. Digite a placa (Mercosul ou antiga).
2. Caminhão já cadastrado: o app traz o cliente e o último hodômetro. Se ele já tem uma OS aberta, o app abre essa
   OS em vez de criar outra.
3. Caminhão novo: escolha o cliente e preencha a marca e o modelo; ele é cadastrado junto.
   - **Cliente:** toque na caixa e os clientes mais recentes aparecem; digite parte do nome, o CNPJ ou o telefone
     para achar qualquer outro. Cliente ainda não cadastrado: digite o nome e toque em **Cadastrar**, informe o
     telefone e se é empresa ou pessoa física. O cliente é criado junto com a OS e o caminhão fica no nome dele; o
     escritório completa o CNPJ/CPF e o endereço depois.
4. Informe o hodômetro, quem trouxe, o problema relatado e os serviços, e confirme.
   - **Serviços:** toque na caixa e o catálogo abre como lista (favoritos e mais usados primeiro). Role e marque
     quantos precisar, ou digite para filtrar, e toque em **Pronto**. Os escolhidos aparecem acima da caixa; toque
     num deles para tirar.

### Dentro da OS no app

- **Situação** e **Localização:** um toque para mudar.
- **Serviços:** adicione pelos favoritos ou pela busca e remova com a lixeira. Serviço já aprovado só o escritório
  remove. Peças do catálogo entram com a etiqueta PEÇA.
- **Fotos:** três blocos, **Entrada** (como o caminhão chegou: frente, laterais, painel e avarias), **Serviço** (o
  defeito e o reparo, que o cliente vê no link) e **Saída** (o caminhão pronto). Cada bloco tem o seu botão
  **Foto**, e o bloco do momento atual da OS fica em destaque. As fotos são reduzidas no próprio celular antes de
  enviar.
- **Checklist:** responda item por item; o progresso aparece na aba.
- **Histórico:** as situações pelas quais a OS passou.
- **Serviço pronto:** quando o trabalho terminar. O escritório vê na hora. Tocou sem querer? Toque em
  **Desfazer** na mensagem que aparece, ou em **Reabrir** depois: a OS volta para o serviço com a situação que
  tinha. Depois que o caminhão é entregue, ou se a OS já está num fechamento mensal ou tem NFS-e, só o escritório
  reabre.
- **Compartilhar** (ícone no topo): manda o link do cliente pelo WhatsApp ou outro app.
- **Editar** (lápis no topo): corrige a placa (de um caminhão novo, que entrou com esta OS), a marca, o modelo, o nº
  de frota, o hodômetro, quem trouxe, o problema e o diagnóstico, e o cliente enquanto ninguém respondeu o orçamento.
  Trocar o cliente leva o caminhão junto, e a OS de uma frota com contrato já fica aprovada, como na abertura.
- **Excluir esta OS** (no fim da folha de edição): para uma OS aberta sem querer, antes de alguém aprovar ou
  concluir; o mecânico exclui só as OS que ele abriu. Um caminhão ou cliente cadastrado só para aquela OS também sai
  (o cliente fica arquivado, e o escritório pode recuperá-lo); um caminhão já conhecido fica, com uma anotação da OS
  excluída. Nos outros casos, o escritório cancela a OS.

### Menu (☰)

Tema claro ou escuro, **Visão do escritório** (só para o escritório), **Guia do sistema**, **Atualizar** e
**Sair**. Um rascunho de OS digitado pela metade fica guardado no celular: uma ligação no meio não apaga o que foi
digitado.

## 7. Clientes e veículos

- **Oficina → Clientes → Clientes:** as frotas e os clientes avulsos. Na aba **Oficina**, marque **Aprovação
  automática** para frotas com contrato. O telefone do cadastro é o que o botão WhatsApp usa.
  - **Digite o CNPJ** e a empresa se preenche pelo cadastro da Receita Federal: razão social, endereço com número,
    complemento e bairro, CEP, cidade com o código IBGE, estado, telefone e e-mail. O endereço sempre segue o CNPJ;
    nome, telefone ou e-mail digitados antes ficam. Tudo continua editável. Empresa que não está ativa na Receita
    mostra um aviso. **Atualizar pela Receita Federal (CNPJ)**, na aba **Vendas e Compras**, traz tudo de novo depois.
  - **Digite o CEP** e a rua, o bairro, a cidade, o estado e o código IBGE se preenchem; número e complemento ficam.
  - Ao digitar o **nome**, o Odoo continua sugerindo empresas do serviço dele; escolher uma dessas sugestões usa
    créditos pagos da Odoo, enquanto a consulta pelo CNPJ é gratuita.
- **Oficina → Clientes → Veículos:** placa, número de frota do cliente, marca, modelo, ano, cor, combustível,
  chassi e último hodômetro. Pelo veículo você vê todas as OS dele.

## 8. Fechamento mensal

Para frotas que pagam uma vez por mês (**Oficina → Faturamento → Fechamento mensal**):

1. **Novo:** escolha o cliente e o período (por padrão, o mês anterior).
2. **Carregar OS do período:** traz as OS concluídas do cliente que ainda não foram fechadas.
3. Confira e **Confirmar**. As OS ficam presas a este fechamento.
4. **Imprimir relatório:** um serviço por linha, com quantidade, preço unitário e valor, e a lista das OS.
5. **Emitir NFS-e:** emite a nota do mês (veja a seção 9). Depois de emitida, o fechamento fica **Faturado**.
   As peças do mês aparecem numa tabela própria no relatório e ficam fora da nota.
6. **Marcar como pago** quando o pagamento entrar.

**Oficina → Faturamento → Análise de serviços** mostra os serviços por período, cliente, setor e mecânico.

## 9. NFS-e

A nota de serviço sai pelo **Sistema Nacional NFS-e**. Há dois modos, escolhidos em **Definições → NFS-e**:

- **Assistido:** o sistema prepara cada valor para você copiar no site do Emissor Nacional. Não precisa de
  certificado.
- **Direto:** o sistema assina e envia a nota sozinho. Precisa do certificado digital A1 da empresa.

### Criar a nota

- **De uma OS concluída** (sem fechamento mensal): botão **Emitir NFS-e** na OS.
- **De um fechamento mensal confirmado:** botão **Emitir NFS-e** no fechamento.
- **Pelo menu NFS-e → Novo:** escolha, no topo, a **Ordem de serviço** ou o **Fechamento mensal**, e a nota se
  preenche sozinha.

Nos três casos a nota traz o cliente, o valor dos serviços, a competência e a **descrição do serviço**, uma linha
por serviço:

```
Serviços referentes à OS 00011, placa NXR4D27 (Mercedes-Benz Axor 2544):
- Carga de gás do ar-condicionado (R-134a): 1 × R$ 320,00 = R$ 320,00
- Troca do filtro secador: 1 × R$ 240,00 = R$ 240,00
Total: R$ 560,00
```

A descrição pode ser editada antes de emitir e aceita até 1000 caracteres. Num fechamento muito grande ela se
encurta sozinha: primeiro sai a lista das OS, depois os serviços menores viram uma linha "Outros serviços". O total
sempre fica.

Uma OS ou um fechamento só pode ter uma nota ativa. Para emitir de novo, cancele a anterior.

### Emitir no modo assistido

1. Na nota, aba **Emissor Nacional**, toque em **Abrir Emissor Nacional**.
2. Copie cada valor (botão de copiar ao lado) para o formulário do site: CNPJ/CPF e nome do cliente, competência,
   código do serviço, valor, alíquota do ISS e descrição.
3. Emita a nota no site e copie a **chave de acesso** (50 dígitos).
4. Cole a chave na nota e toque em **Registrar nota emitida**.

No modo direto, o botão **Emitir NFS-e** da nota faz tudo isso sozinho. Nos dois modos, o **DANFSe** (PDF da nota) fica
disponível depois da emissão, e uma nota emitida pode ser cancelada pelo botão **Cancelar NFS-e**.

> **Peças:** as linhas marcadas como **Peça** ficam fora da nota. O valor e a descrição cobrem só a mão de obra,
> porque peça é faturada como mercadoria (ICMS), fora da nota de serviço. Uma OS só com peças não tem NFS-e.

## 10. Configurações

Só o administrador vê **Oficina → Configuração → Definições**.

### Marca

- **Cor de destaque:** pinta botões e destaques em todo o sistema, no app, na página do cliente e no login.
- **Cor de fundo e cartão do login:** a tela de entrada, clara ou escura.
- **Logos:** logo completo para fundo claro (PDFs, login claro) e para fundo escuro (painel, login escuro), o
  símbolo (cabeçalho do app) e o símbolo para o tema claro.
- **Ícone do navegador:** a figura da aba e dos atalhos no celular (.ico ou .png).
- **Imagem de pré-visualização de links:** o que aparece quando um link é compartilhado no WhatsApp (1200×630).

### Textos

A **garantia** impressa em cada OS e os **termos** que o cliente aceita ao aprovar.

### Fotos

Onde as fotos ficam guardadas:

- **Banco de dados** (padrão): funciona em qualquer servidor, sem configurar nada.
- **Cloudinary:** deixa o banco menor e as fotos carregam mais rápido. No Cloudinary, abra **Settings (a
  engrenagem) → API Keys** e copie:
  - **Cloud name:** o nome no topo da página;
  - **Chave de API:** o **número** da coluna "API Key", não o nome da chave (como "Root");
  - **Segredo da API:** o "API Secret" da mesma linha, que aparece ao tocar no olho;
  - **Pasta:** o nome que você quiser. O Cloudinary cria a pasta sozinho na primeira foto.

  Depois toque em **Testar conexão**: o sistema envia uma foto de teste para a pasta e a apaga. As fotos já tiradas
  continuam onde estavam.

### Cadastros da oficina (menu Configuração)

- **Serviços:** nome, setor, horas e preço. Os marcados como **favoritos** aparecem primeiro no app. Marque
  **Peça** nas peças e materiais, e eles já chegam marcados na OS.
- **Situações:** as colunas do quadro, na ordem da oficina, com cor. O tempo numa **situação de espera** (peças,
  aprovação) não conta como tempo de trabalho.
- **Localizações:** boxes, pátio, "em teste na rua", "no cliente".
- **Setores:** elétrica, ar-condicionado, injeção eletrônica etc.
- **Checklists:** os itens do checklist de entrada e de saída, por seção.

### Usuários

**Definições → Usuários e empresas → Usuários → Novo:** nome, login (e-mail ou apelido) e, no campo **Oficina**,
**Mecânico** ou **Escritório**. Depois de salvar, defina a senha em **⚙ Ação → Alterar senha** e passe-a à
pessoa, que pode trocá-la em **Minhas preferências**.

## 11. Dúvidas frequentes

**O sistema pediu a senha de novo.** O login expira depois de uma semana sem uso. Entre de novo.

**Estou sem internet no pátio.** O app precisa de conexão (Wi-Fi ou 4G). O que já estava digitado numa OS nova fica
guardado no celular até a conexão voltar.

**Uma foto não subiu.** Aparece o aviso "Foto não enviada" com o motivo. Confira a conexão e tente de novo. Se as
fotos vão para o Cloudinary, peça ao administrador para usar **Testar conexão** nas Definições.

**O link do cliente não foi copiado.** Alguns navegadores bloqueiam a cópia automática. O link aparece na tela para
copiar à mão.

**Apareceu uma OS sem número ("Novo").** Ela ainda não foi salva: toque em **Salvar**.

**O mecânico não vê o botão Aprovar.** Aprovar é do escritório. Se ele precisa aprovar, mude o perfil dele para
Escritório.

**Quero ver o guia de novo.** Menu do usuário → **Guia do sistema** (no app: ☰ → **Guia do sistema**).
