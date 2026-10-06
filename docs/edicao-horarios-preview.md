# Edição de horários na pré-visualização

## Resumo do entendimento

- Depois de gerar a folha ponto, o usuário edita **somente os horários** (entrada, intervalo saída, intervalo entrada, saída) **clicando na caixa** e digitando.
- Cada caixa é **independente**; não há recálculo de 8h nem de outros campos do dia.
- Gerar de novo ou atualizar **apaga** as edições manuais.
- Vale no **Relatório** e no **Relatório Efetivado**.
- O download grava o PDF **já com** as alterações.
- Objetivo: corrigir um dia pontual sem rodar o CCU de novo.

## Premissas

- Um usuário, PDF local; sem sync, histórico ou permissões extras.
- A pré-visualização reflete a edição **antes** do download.
- Formato `HH:MM`; valor inválido não entra na caixa.
- Assinatura, cabeçalho e página 2 **não** se editam.
- Fim de semana / feriado: caixa de horário vazia pode ser preenchida; `SÁBADO`/`DOMINGO` na coluna Entrada **não** são substituídos.
- A edição ocorre na folha já gerada, sem chamar o robô.

## Log de decisões

| Decisão | Alternativas | Motivo |
|---|---|---|
| Editar só horários nas caixas | Texto livre, visto, página 2 | Correção pontual da jornada sem editor de PDF genérico |
| Células independentes | Recalcular saída / avisar 8h | Controle total do que foi digitado |
| Gerar/atualizar descarta edições | Persistir / perguntar | Estado simples; fonte da verdade volta a ser CCU + regras |
| Relatório e Efetivado | Só uma das telas | O `PdfViewer` e o overlay são os mesmos |
| Clique na caixa do preview | Tabela ao lado / tabela + Aplicar | UX alinhada à folha; a grade PDF já é detectada |
| Sem undo fino | Histórico de edições | YAGNI; gerar de novo resolve |

## Desenho

### Arquitetura

O PDF gerado permanece a base. A edição não altera CSV nem CCU: só o overlay da folha montada, até download ou novo generate.

1. Gerar relatório → grade detectada + overlay + `saida.pdf` + imagens no viewer.
2. Guardar em memória a grade (colunas/linhas em pontos PDF) e os horários atuais por dia.
3. Clique no preview → pixel da imagem (zoom + padding) → ponto PDF → célula `(dia, coluna)`.
4. Se for uma das quatro colunas de horário, abrir campo `HH:MM`.
5. Confirmar → redesenhar aquele texto no overlay (recuo branco se necessário) → merge na página 1 → atualizar a imagem.
6. Download copia esse `saida.pdf`. Refresh/gerar zera o estado em memória.

O `PdfViewer` (Relatório e Efetivado) trata o clique. Mapear célula e gravar hora ficam junto de gerador/grade, compartilhados.

Sem histórico, sem edição da página 2.

### Clique e validação

- Clique só na **página 1**. Fora das colunas de horário, cabeçalho, Dia, Visto ou Autorização: no-op.
- Imagem em `CONTAIN` no card (`BASE_WIDTH * zoom`, padding 12). Conversão usa a área útil da imagem, não o card inteiro.
- Campo sobre a célula ou dialog curto. Enter confirma; Esc / clique fora cancela.
- Aceita `H:MM` ou `HH:MM` (`8:05` → `08:05`). Inválido: aviso, não grava. Vazio apaga o horário da caixa.
- `SÁBADO`/`DOMINGO` na Entrada não são substituídos. Intervalo pré-impresso pode ser coberto pelo overlay.

### Erros e limites

- Sem PDF / clique antes do preview: ignora.
- Grade ausente: edição desligada.
- Falha ao mesclar: mantém o último PDF bom e mostra o dialog de erro já existente.
- Uma célula por vez; sem multi-edit.
- Risco principal: clique errar a caixa com zoom. Mitigação: coordenadas da grade em pontos PDF + bounding box real da imagem.

### Testes manuais

- Relatório e Efetivado: Entrada dia 3 → `08:07` visível no preview e no PDF baixado.
- Trocar intervalo sem alterar as outras caixas do dia.
- Apagar uma saída.
- Clique em Entrada de sábado não substitui `SÁBADO`.
- Zoom in/out e o mesmo clique.
- Atualizar/gerar descarta edições.
- `abc` e `25:00` não gravam.
