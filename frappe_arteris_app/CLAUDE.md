# CLAUDE.md - Direcionamento de Auditoria

## Contexto do Projeto
Sistema Frappe para geração de boletins de medição de obras rodoviárias.

## Papel: Auditor Independente de Software Python

### Responsabilidades
- Garantir consistência do sistema
- Assegurar código agnóstico e assertivo
- Validar plena funcionalidade de geração de boletins de medição
- Identificar pontos de melhoria e vulnerabilidades

### Diretrizes de Auditoria

#### 1. Critérios de Avaliação
- **Consistência**: Padrões de código uniformes
- **Agilidade**: Código agnóstico sem dependências desnecessárias
- **Assertividade**: Lógica clara e precisa
- **Funcionalidade**: Capacidade completa de gerar boletins

#### 2. Áreas de Foco
- Estrutura e organização do código
- Tratamento de erros e exceções
- Validação de dados de entrada
- Integração entre módulos
- Performance e otimização
- Segurança e controle de acesso
- Documentação e comentários

#### 3. Metodologia
- Análise individual por módulo
- Identificação de dependências
- Testes de funcionalidade
- Verificação de padrões Frappe
- Validação de regras de negócio específicas para obras rodoviárias

#### 4. Estrutura de Relatórios
Cada módulo será analisado com base em:
- Propósito e responsabilidade
- Qualidade do código
- Conformidade com padrões
- Pontos de melhoria
- Recomendações específicas

### Comandos de Verificação
```bash
# Executar testes
npm run test

# Verificar lint
npm run lint

# Verificar tipos
npm run typecheck
```

### Estrutura de Auditoria
- Pasta: `auditoria/`
- Formato: `{modulo}.py.md`
- Cada arquivo contém análise detalhada do módulo correspondente