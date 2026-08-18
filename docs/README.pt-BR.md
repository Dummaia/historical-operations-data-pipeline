# Pipeline Histórico de Dados Operacionais

[Voltar ao README principal](../README.md)

Pipeline ETL em Python que transforma versões datadas de planilhas Excel com
cinco abas em uma base histórica confiável, rastreável e pronta para análise.

## Contexto

Arquivos armazenados ao longo do tempo não formam um histórico por si só. Para
reconstruir a evolução de um processo, é necessário descobrir cada versão,
normalizar a estrutura, validar a qualidade, selecionar a posição correta de
cada dia e preservar a origem de todos os registros.

A implementação original consolidou **mais de 64.432 registros de 12 arquivos**.
Esta edição pública reproduz a arquitetura com dados inteiramente fictícios.

## Principais capacidades

- leitura automática de arquivos `.xlsx` e `.xlsm`;
- processamento das cinco faixas operacionais;
- normalização de colunas, textos, identificadores, números e datas;
- remoção de linhas inválidas e duplicidades exatas;
- uma posição por processo e data de referência;
- rastreabilidade por arquivo, aba, ordem e linha original;
- extração da data do acompanhamento;
- geração de Parquet, Excel formatado e relatório JSON;
- persistência opcional no PostgreSQL;
- testes automatizados e integração contínua.

## Execução rápida

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"

historical-pipeline generate-sample --output data/sample --snapshots 3 --records 27

historical-pipeline run `
  --input data/sample `
  --output output `
  --config config/pipeline.toml
```

O comando gera:

- `output/historical_operations.parquet`;
- `output/historical_operations.xlsx`;
- `output/quality_report.json`.

## Segurança

O repositório não utiliza nomes de empresas reais, destinatários, credenciais,
caminhos de rede, URLs privadas ou identificadores corporativos. Os arquivos de
exemplo são gerados localmente e contêm somente dados sintéticos.
