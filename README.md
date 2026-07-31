# iFlower

Marketplace demonstrativo de flores, cestas e presentes, desenvolvido com Django. A primeira versão simula a jornada completa entre cliente e vendedor: descoberta, personalização, carrinho, checkout, pagamento, acompanhamento, atualização de status e avaliação.

> Todos os usuários, lojas, endereços, produtos, pedidos e valores deste repositório são fictícios. Pagamento, estoque, disponibilidade, áreas de atendimento, entrega e rastreamento são simulações para portfólio.

## Objetivo

Demonstrar uma aplicação web de marketplace completa, responsiva e segura, sem gateways, mapas, transportadoras ou serviços externos pagos. Nenhum número de cartão é solicitado ou armazenado.

## Funcionalidades

![Página inicial do iFlower](docs/home-desktop.png)

- Página inicial, busca, categorias, lojas e catálogo com filtros e paginação;
- páginas detalhadas de loja e produto, com galeria e personalizações;
- cadastro de cliente, login/logout e recuperação de senha pelo console;
- perfil e endereços de entrega;
- carrinho multi-loja agrupado por vendedor, seleção individual ou por loja e contador na navbar;
- checkout atômico de uma loja por vez, preservando no carrinho os itens das demais lojas;
- confirmação automática opcional e configurável por loja;
- preenchimento assistido de endereço por CEP e opção de exibir/ocultar senhas;
- pedido com snapshot dos produtos e do endereço;
- Pix, cartão e pagamento na entrega simulados, sem dados financeiros reais;
- linha do tempo de acompanhamento simulada e imutável para vendedores;
- avaliação exclusiva para pedidos entregues e limitada a uma por pedido;
- painel do vendedor com métricas, pedidos, produtos e edição da loja;
- dashboard administrativo visual e Django Admin;
- seed idempotente e testes automatizados de fluxo e segurança;
- páginas 404/500 personalizadas e interface responsiva.

## Tecnologias

- Python 3.13;
- Django 6.0.7;
- SQLite já configurado no projeto inicial;
- Django Templates, HTML5, CSS3 e JavaScript;
- Bootstrap 5 para componentes básicos;
- Pillow para validação e upload de imagens.
- ViaCEP para preenchimento progressivo do endereço no navegador.

O Pillow é a única dependência adicionada ao projeto original. Ele é necessário para `ImageField` e validação das imagens enviadas.

## Estrutura

O repositório recebido já continha um único app vazio, `iflower`. Como não havia domínio nem migrações desse app, a implementação preserva a estrutura existente e separa responsabilidades por módulo:

```text
iflower/
├── admin.py                 # Django Admin
├── decorators.py            # controle de acesso do vendedor
├── forms.py                 # forms e ModelForms
├── management/commands/     # seed_demo
├── migrations/              # esquema do domínio
├── models.py                # catálogo, carrinho, pedidos e avaliações
├── services.py              # checkout e transições de status
├── tests.py                 # testes do fluxo e permissões
├── urls.py                  # rotas nomeadas
└── views.py                 # páginas públicas e painéis
templates/                   # base, componentes e páginas
static/css/iflower.css       # identidade visual responsiva
static/js/iflower.js         # seleções do carrinho, senhas e preenchimento por CEP
media/demo/                  # imagens demonstrativas locais
```

## Modelos principais

- `Profile` e `Address`;
- `Store` e `ServiceArea`;
- `Category`, `Product`, `ProductImage` e `CustomizationOption`;
- `Cart` e `CartItem`;
- `Order`, `OrderItem`, `SimulatedPayment` e `StatusHistory`;
- `Review`.

O usuário padrão do Django foi preservado porque as migrações de autenticação já estavam aplicadas. Os papéis de cliente e vendedor são representados por `Profile`; administradores usam `is_staff`/`is_superuser`.

## Instalação

No PowerShell, a partir da raiz do projeto:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

Acesse `http://127.0.0.1:8000/`.

### Variáveis de ambiente

Nenhuma variável é obrigatória para a demonstração local. Em um ambiente que não seja exclusivamente de desenvolvimento, defina:

```powershell
$env:DJANGO_SECRET_KEY = 'gere-um-segredo-seguro'
```

Não use a chave ou as credenciais demonstrativas em produção. Banco, `DEBUG`, hosts e deploy devem ser configurados para o ambiente antes de qualquer publicação.

## Usuários de demonstração

Todos usam a senha `Demo123!`.

| Perfil | E-mail |
| --- | --- |
| Administrador | `admin@iflower.local` |
| Cliente | `cliente@iflower.local` |
| Vendedor Floratta | `floratta@iflower.local` |
| Vendedor Encanto | `encanto@iflower.local` |
| Vendedor Doce Afeto | `doceafeto@iflower.local` |

O seed pode ser executado várias vezes. Ele atualiza os registros conhecidos sem duplicar o conjunto demonstrativo.

## Rotas principais

| Área | Rota |
| --- | --- |
| Início | `/` |
| Lojas | `/lojas/` |
| Catálogo | `/presentes/` |
| Quero vender | `/quero-vender/` |
| Carrinho | `/carrinho/` |
| Checkout | `/checkout/` |
| Meus pedidos | `/pedidos/` |
| Painel do vendedor | `/vendedor/` |
| Dashboard administrativo | `/gestao/` |
| Django Admin | `/admin/` |

## Verificações

```powershell
python manage.py makemigrations --check --dry-run
python manage.py check
python manage.py test
```

Os testes verificam cadastro e login, perfis, propriedade de loja/produto, carrinho multi-loja, seleção de itens e lojas, contador, subtotais, taxas, estoque, checkout de uma loja por vez, confirmação automática opcional, snapshot, pagamento, limpeza seletiva do carrinho, transições válidas e inválidas, isolamento entre clientes/vendedores e regras de avaliação.

## Segurança implementada

- CSRF em todos os formulários de mutação;
- consultas privadas sempre filtradas pelo cliente ou dono da loja;
- upload limitado a JPG, JPEG, PNG ou WebP, com até 5 MB;
- `Decimal` para valores monetários;
- `transaction.atomic` e bloqueios no checkout/transições;
- preços e estoque recalculados no backend;
- sem armazenamento de dados reais de pagamento;
- histórico sem permissão de alteração/exclusão no painel do vendedor e no Admin.

## Dados e imagens

As três lojas ficam em Rio Verde, Goiás, apenas para ambientação. Endereços e contatos não representam pessoas ou estabelecimentos reais.

As quatro imagens em `media/demo/` foram geradas especificamente para este projeto com a ferramenta integrada de geração de imagens da OpenAI. São assets locais, sem hotlink, texto, logotipos ou marcas de terceiros. Cada produto do seed recebe uma imagem compatível com sua categoria.

## Limitações desta versão

- pagamento e estorno não são reais;
- entrega, rastreamento, horários, taxas e áreas atendidas são simulados;
- o estoque é demonstrativo e não possui reserva temporária;
- cada vendedor administra uma única loja;
- a confirmação automática de pedidos vem ativa por padrão nesta versão; antes da produção, o padrão deve ser revisto para exigir confirmação da loja;
- não há cupons reais, geolocalização, notificações, mensageria ou integração externa;
- Bootstrap é carregado por CDN; a lógica principal permanece funcional sem APIs externas;
- o autocomplete usa o [ViaCEP](https://viacep.com.br/) após a digitação de um CEP válido; se o serviço estiver indisponível, todos os campos permanecem editáveis manualmente;
- SQLite foi mantido porque era o banco previamente configurado. Para produção, configure o banco existente do ambiente sem versionar credenciais.

## Próximos passos

- separar o domínio em apps quando a equipe e o produto crescerem;
- usar PostgreSQL, storage de objetos e processamento assíncrono em produção;
- incluir calendário de disponibilidade e reserva temporária de estoque;
- adicionar observabilidade, auditoria administrativa e testes end-to-end contínuos;
- integrar pagamentos, entrega e notificações somente após requisitos legais e operacionais reais.
