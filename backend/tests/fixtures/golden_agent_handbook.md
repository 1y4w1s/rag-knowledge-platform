# Golden Agent Handbook v1.0

## gitignore_intro

GitHub .gitignore collection purpose is to populate the .gitignore template choosers that appear when you create a new repository on GitHub. The gitignore repo uses the CC0-1.0 license. Versioned templates should be placed in the community/ directory. The recommended contribution workflow is: Fork, Create a branch, Make changes, Send a pull request.

A good gitignore template is a set of rules to help Git repositories work efficiently with specific tools and frameworks. For version-specific template changes, keep evergreen at root, previous versions in community/. The Global directory in the gitignore repo contains templates for editors, tools and operating systems. Specialized templates live in the community directory.

The gitignore collection does NOT aim to cover every project possible. To contribute non-mainstream templates, add to community directory.

## docker_compose

Docker Compose is a tool to Define and run multi-container Docker applications. The file format Compose uses is YAML. The command to start Compose services is docker compose up. To stop Compose services, use docker compose down. The file Compose looks for by default is compose.yaml.

Compose can rebuild images before starting with docker compose up --build. To view Compose service logs, use docker compose logs. The difference between docker-compose and docker compose is v1 vs v2, docker compose is the current plugin version. Compose can manage multiple containers to Define and run multi-container Docker applications. The command docker compose ps will list containers managed by Compose.

## fastapi_intro

FastAPI is a modern, fast web framework for building APIs with Python. FastAPI can auto-generate interactive API documentation (Swagger UI). The protocol FastAPI uses is ASGI. FastAPI uses Python type hints for validation. The server commonly used with FastAPI is Uvicorn. Pydantic is used in FastAPI for data validation and settings management.

FastAPI is built on top of Starlette for web parts and Pydantic for data parts. FastAPI does support async: Yes, built on ASGI with async support. FastAPI handles path operations with decorators like @app.get(), @app.post(). Dependency injection in FastAPI uses Depends() for reusable components.

The web framework that uses Uvicorn as its ASGI server is FastAPI. The standard port for web servers created with FastAPI is 8000.

## react_intro

React is A JavaScript library for building user interfaces. React composes UIs using components. The syntax extension React uses is JSX. The virtual DOM is React internal representation of the UI. A React hook is functions that let you use state and lifecycle in function components. useState returns a stateful value and a function to update it.

The useEffect hook is for side effects in function components. JSX is a syntax extension that looks like HTML in JavaScript. React handles events with camelCase event handlers like onClick. The key prop is used in lists to help React identify which items changed.

The React feature that allows managing state in function components is the useState hook.

## pgvector_intro

pgvector is Open-source vector similarity search for PostgreSQL. The index types pgvector supports are IVFFlat and HNSW. The distance functions in pgvector are L2, inner product, cosine distance represented by operators: <=> for cosine distance, <-> for L2 distance, <#> for inner product.

The PostgreSQL version required for pgvector is PostgreSQL 11+. HNSW is a Hierarchical Navigable Small World graph index. pgvector can use indexing for approximate search: Yes, IVFFlat and HNSW indexes. pgvector supports exact nearest neighbor search: Yes, without using an index.

The database technology that pgvector extends is PostgreSQL.

## sqlalchemy_intro

SQLAlchemy is a SQL toolkit and ORM for Python. The two main components of SQLAlchemy are Core and ORM. SQLAlchemy ORM is an Object-Relational Mapping layer. A SQLAlchemy session is a workspace for ORM operations. SQLAlchemy Core is a lower-level SQL abstraction layer.

The databases SQLAlchemy supports include PostgreSQL, MySQL, SQLite, Oracle, MSSQL. Alembic is a database migration tool built on SQLAlchemy. SQLAlchemy handles connections through Engine and connection pool. A SQLAlchemy model is a Python class mapped to a database table. The SQLAlchemy Unit of Work pattern tracks changes and flushes to DB.

The tool used for database migrations with SQLAlchemy is Alembic. The SQLAlchemy pattern that automatically tracks object changes is Unit of Work.

## pytest_intro

pytest is a mature full-featured Python testing tool. pytest discovers tests by looking for test_ prefixed functions. A pytest fixture is functions that provide test data or setup. The plugin system pytest uses includes conftest.py and hook system. pytest can run unittest tests: Yes, pytest supports unittest TestCase.

pytest.mark provides decorators for test metadata. pytest.parametrize can run a test with multiple sets of arguments. conftest.py is a shared fixtures configuration file. The pytest assert introspection provides detailed failure messages without extra code. pytest supports parallel test execution: Yes via pytest-xdist plugin.

The testing framework that can run unittest-style tests is pytest.

## tailwind_intro

Tailwind CSS is a utility-first CSS framework. Tailwind differs from Bootstrap because it provides low-level utility classes instead of pre-built components. A utility-first framework is a framework with small single-purpose CSS classes. Tailwind can be customized: Yes via tailwind.config.js.

Purge in Tailwind means removing unused CSS in production build. Tailwind supports responsive design: Yes with sm:, md:, lg: prefixes. The @tailwind directives are @tailwind base, components, utilities. Tailwind can be used with React: Yes, works with any framework. The Tailwind JIT mode is just-in-time compilation for smaller builds. To group hover styles in Tailwind, use the hover: prefix.

The CSS framework that provides utility classes for React components is Tailwind CSS.

## uvicorn_intro

Uvicorn is an ASGI web server for Python. The protocols Uvicorn supports are HTTP/1.1 and WebSocket. Uvicorn is production-ready: Yes, used in production. To reload Uvicorn on code changes, use the uvicorn --reload flag. The default Uvicorn port is 8000.

## python311_changes

The main Python 3.11 performance improvement is that CPython is up to 10-60% faster. PEP 657 provides Enhanced error locations in tracebacks. The Self type (PEP 673 Self type for class methods) is the Self type for returning self from class methods. Python 3.11 introduces except* (PEP 654 Except* for ExceptionGroups). The Variadic Generics feature is PEP 646 Variadic Generics.
