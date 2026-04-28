# Especificação funcional — Consulta de Matriz Física, Endereçamento e Estoque Min/Max

## 1. Objetivo

Evoluir o módulo de estoque para padronizar o endereçamento físico dos itens, restringir a seleção por filial e adicionar o gerenciamento de estoque mínimo e máximo na visão expandida do produto, incluindo estoque de segurança calculado automaticamente com base no histórico de entrada e saída.

A proposta segue práticas comuns de WMS/ERP: localização padronizada por cadastro mestre, uso de endereço único por posição física, política de reposição Min/Max com monitoramento contínuo e cálculo de estoque de segurança baseado em variabilidade e lead time [web:27][web:31][web:34][web:40][web:55][web:60].

## 2. Contexto do problema

Hoje a tela **Consulta de Matriz Física** permite visualizar saldos, porém o endereçamento de estoque não está tratado como um dado estruturado e padronizado. Isso abre espaço para inconsistências de escrita, divergência entre usuários e baixa confiabilidade para consulta operacional.

Também existe a necessidade de levar o mesmo comportamento para o fluxo de **Inbound**, garantindo que a entrada de mercadoria já nasça com a localização correta e vinculada à filial apropriada. Em paralelo, a operação precisa de um controle simples e objetivo de **estoque mínimo e máximo** por produto, agora acrescido de **estoque de segurança** calculado automaticamente para produtos definidos como controlados por lote ou por ativo.

## 3. Escopo funcional

### 3.1 Aba Saldos e Localizações

Na tela **Consulta de Matriz Física**, dentro do explorer do produto, deve existir uma nova aba chamada **Saldos e Localizações**.

A aba deve exibir, no mínimo:
- Produto.
- Filial.
- Polo/doca, mantendo este campo inalterável.
- Endereçamento de estoque.
- Quantidade disponível.
- Quantidade reservada.
- Quantidade total.

O campo **Endereçamento de estoque** deve ser editável via **Listbox** com as localizações previamente cadastradas na tela de configurações, evitando digitação livre e garantindo padronização [web:27][web:32].

### 3.2 Regra por filial

A seleção de endereçamento deve ser limitada apenas às localizações pertinentes à filial do registro atual. Isso impede que o usuário grave uma localização de outra unidade operacional e preserva a consistência logística.

O filtro deve ser aplicado em tempo de consulta e também em tempo de edição, de forma que a lista exiba somente localizações válidas para a filial selecionada. Caso o endereço seja desativado ou fique incompatível depois de já atribuído, o sistema deve sinalizar a inconsistência para correção.

### 3.3 Regra para Polo/doca

A coluna de **Polo/doca** deve permanecer **inalterável** nesta entrega, servindo apenas como informação legada/consultiva. O novo controle de localização deve nascer em campo separado, com governança própria e sem risco de impactar a lógica já existente.

### 3.4 Endereçamento no inbound

Na entrada do produto, dentro do **Inbound**, a mesma funcionalidade deve ser aplicada com as mesmas regras de negócio.

Isso significa:
- seleção por Listbox;
- uso exclusivo de localizações previamente cadastradas;
- validação por filial;
- impedimento de gravação com endereço fora da unidade;
- consistência entre entrada, consulta e estoque disponível.

## 4. Estoque mínimo e máximo

Na tela expandida do produto, deve ser criada uma nova aba para gerir **estoque mínimo e máximo**.

A aba deve permitir configurar por produto, e opcionalmente por filial, os seguintes parâmetros:
- Estoque mínimo.
- Estoque máximo.
- Unidade de medida.
- Status ativo/inativo.
- Observações.

A solução deve ser simples, operacional e auditável. Sistemas maduros de reposição usam Min/Max como gatilho para manter disponibilidade e reduzir ruptura, normalmente monitorando o nível mínimo e apontando quando o saldo cai abaixo dele [web:31][web:34][web:37].

## 5. Estoque de segurança

A solução deve incluir uma aba ou bloco de configuração para **estoque de segurança**, calculado automaticamente pelo sistema com base no histórico de entradas e saídas, de forma a proteger a operação contra variabilidade de consumo e reposição [web:55][web:56][web:60][web:61].

### 5.1 Regra de cálculo

O cálculo padrão deve considerar ao menos:
- Consumo histórico por período.
- Variabilidade da demanda.
- Lead time médio ou parametrizado.
- Nível de serviço desejado.

Uma abordagem prática e bem aceita é usar a lógica baseada em variabilidade e nível de serviço, como `Z x desvio padrão da demanda x raiz do lead time`, ou fórmula equivalente definida pelo time de negócio [web:55][web:57][web:62][web:65].

### 5.2 Fonte de dados

O sistema deve usar o histórico de movimentos de estoque, preferencialmente entradas e saídas confirmadas, para calcular o estoque de segurança de forma dinâmica. Caso exista sazonalidade ou item com pouca movimentação, o cálculo deve permitir tratamento diferenciado ou revisão manual.

### 5.3 Regras de ativação

A funcionalidade de estoque de segurança deve ser opcional por produto e por filial. Além disso, deve existir a possibilidade de ativar apenas para produtos controlados por **lote** ou **ativo**, com prioridade para itens controlados por lote, já que esse tipo de controle costuma exigir rastreabilidade e disciplina maior na reposição [web:63][web:69].

### 5.4 Comportamento do sistema

- Quando ativado, o sistema calcula automaticamente o estoque de segurança.
- O usuário pode visualizar o valor calculado, mas não sobrescrevê-lo sem permissão especial.
- O estoque mínimo pode ser influenciado pelo estoque de segurança, conforme regra definida.
- O sistema deve recalcular sempre que houver mudança relevante no histórico, lead time ou janela de análise.

### 5.5 Sugestão de interface

Na aba de Min/Max, incluir:
- Estoque de segurança calculado.
- Origem do cálculo.
- Janela histórica usada.
- Lead time considerado.
- Nível de serviço.
- Botão de simulação/recalcular.

## 6. Regras de negócio

### 6.1 Endereçamento

- O endereçamento deve ser selecionado apenas a partir do cadastro mestre de localizações.
- Não deve existir digitação manual livre no campo principal.
- O código da localização deve ser único por contexto de filial, salvo regra de negócio explícita em contrário.
- Toda alteração deve manter histórico de auditoria.

### 6.2 Validação por filial

- Uma localização só pode aparecer na lista se estiver vinculada à filial do documento, do item ou do movimento.
- Se o usuário tentar copiar ou importar um endereço de outra filial, o sistema deve bloquear a operação e exibir mensagem clara.
- Caso a filial do registro seja alterada após a escolha do endereço, o sistema deve revalidar a localização.

### 6.3 Min/Max

- O estoque mínimo não pode ser maior que o máximo.
- O máximo não pode ser menor que o mínimo.
- Quando o saldo disponível for menor ou igual ao mínimo, o sistema deve sinalizar necessidade de reposição.
- Quando o saldo atingir o máximo, o sistema deve indicar faixa cheia, evitando excesso de abastecimento.

## 7. Melhorias recomendadas

### 7.1 Separar cadastro de localização de uso operacional

Sugiro tratar localização como um **cadastro mestre** com estrutura hierárquica, por exemplo: filial, zona, rua, nível, posição e tipo de armazenamento. Isso melhora escalabilidade e reduz ambiguidade, como é comum em sistemas de bin location e WMS [web:27][web:30][web:32].

### 7.2 Máscara e padronização visual

Além da Listbox, vale exibir a localização com código curto e descrição amigável, como `SP-01 > A-03 > N2 > P04`. Isso acelera conferência operacional e reduz erro humano, especialmente em ambientes com alto volume [web:26][web:36].

### 7.3 Busca e filtro rápidos

Se houver muitas localizações por filial, a Listbox deve suportar busca incremental, ordenação alfabética e filtro por zona/tipo. Isso evita que uma lista longa prejudique a experiência do usuário.

### 7.4 Auditoria e rastreabilidade

Toda alteração de endereço, mínimo e máximo deve registrar usuário, data, hora, origem da mudança e valor anterior. Em estoque, rastreabilidade é crítica para análise de divergência e investigação de erro operacional.

### 7.5 Regras de alerta

Sugiro incluir alertas visuais no produto:
- abaixo do mínimo: alerta vermelho ou amarelo;
- entre mínimo e máximo: estado normal;
- acima do máximo: alerta de excesso.

Isso evita que o usuário precise interpretar número bruto o tempo todo.

## 8. Fluxo sugerido

### 8.1 Cadastro de localização

1. Usuário cadastra localizações na tela de configurações.
2. Cada localização recebe filial, código, descrição e status.
3. O sistema passa a usar esse cadastro como fonte única para o endereçamento.

### 8.2 Consulta de matriz física

1. Usuário abre o explorer do produto.
2. A aba **Saldos e Localizações** exibe as posições por filial.
3. O usuário seleciona o endereçamento na Listbox, respeitando a filial.
4. O sistema grava e audita a alteração.

### 8.3 Inbound

1. O operador recebe a mercadoria.
2. No momento da entrada, escolhe a localização permitida para a filial.
3. O sistema valida a consistência e conclui o movimento.

### 8.4 Min/Max

1. Usuário acessa a aba expandida do produto.
2. Informa mínimo e máximo por regra de negócio.
3. O sistema monitora o saldo e aponta situação de reposição.

## 9. Modelo de dados sugerido

### 9.1 Tabela de localizações

Campos sugeridos:
- id
- filial_id
- codigo
- descricao
- zona
- doca_polo
- status
- created_at
- updated_at
- created_by
- updated_by

### 9.2 Tabela de saldo por localização

Campos sugeridos:
- id
- produto_id
- filial_id
- localizacao_id
- saldo_disponivel
- saldo_reservado
- saldo_total
- updated_at

### 9.3 Tabela de min/max

Campos sugeridos:
- id
- produto_id
- filial_id
- estoque_minimo
- estoque_maximo
- unidade_medida
- ativo
- observacao
- created_at
- updated_at
- created_by
- updated_by

### 9.4 Tabela de estoque de segurança

Campos sugeridos:
- id
- produto_id
- filial_id
- controle_por_lote (boolean)
- controle_por_ativo (boolean)
- ativo (habilita o cálculo)
- janela_historica_dias
- lead_time_dias
- nivel_de_servico
- desvio_padrao
- estoque_seguranca_calculado
- created_at
- updated_at
- updated_by

## 10. Critérios de aceitação

- A aba **Saldos e Localizações** deve existir na consulta do produto.
- O campo de endereçamento deve usar Listbox com localizações cadastradas.
- O campo deve respeitar o filtro por filial.
- A coluna de Polo/doca deve permanecer sem edição.
- O inbound deve usar a mesma regra.
- A aba de Min/Max deve permitir salvar, editar e consultar parâmetros por produto.
- O sistema deve bloquear mínimo maior que máximo.
- O sistema deve registrar auditoria das alterações.
- O estoque de segurança deve ser calculado automaticamente quando ativado.
- O cálculo deve considerar apenas produtos com controle por lote ou ativo, conforme regra.
- O sistema deve exibir o valor de estoque de segurança e permitir simulação/recálculo.

## 11. Riscos e cuidados

- Cadastro de localização incompleto pode bloquear operação no inbound.
- Lista muito grande sem busca pode prejudicar usabilidade.
- Filial mal configurada pode ocultar localizações válidas.
- Falta de auditoria pode gerar divergência entre físico e sistema.
- Cálculo de estoque de segurança sensível ao histórico pode gerar valores instáveis em itens com pouca movimentação.

## 12. Recomendação final

A melhor abordagem é implementar isso em três camadas: primeiro o **cadastro mestre de localizações com validação por filial**, depois a **camada operacional** na consulta do produto e no inbound. Em seguida, adicionar a aba de **Min/Max** com validação simples e alertas de reposição, e por fim incorporar o **estoque de segurança calculado automaticamente**, ativo por produto/filial, com foco em itens controlados por lote [web:27][web:31][web:40][web:55][web:63].
