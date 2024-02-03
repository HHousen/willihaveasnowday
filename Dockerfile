# syntax = docker/dockerfile:1

# Adjust NODE_VERSION as desired
ARG NODE_VERSION=21.5.0
FROM node:${NODE_VERSION} as base

LABEL fly_launch_runtime="Node.js"

# Node.js app lives here
WORKDIR /app

# Set production environment
ENV NODE_ENV="production"


# Throw-away build stage to reduce size of final image
FROM base as build

# Install packages needed to build node modules
RUN apt-get update -qq && \
    apt-get install --no-install-recommends -y build-essential node-gyp pkg-config python-is-python3

# Install node modules
COPY --link package-lock.json package.json ./
RUN npm ci --include=dev

# Copy application code
COPY --link . .

# Build application
RUN npm run build

# Remove development dependencies
RUN npm prune --omit=dev


# Final stage for app image
FROM base

ENV HOME="/root"
WORKDIR ${HOME}
RUN apt-get update -qq && apt-get install --no-install-recommends -y git curl
RUN git clone --depth=1 https://github.com/pyenv/pyenv.git .pyenv
ENV PYENV_ROOT="${HOME}/.pyenv"
ENV PATH="${PYENV_ROOT}/shims:${PYENV_ROOT}/bin:${PATH}"

ENV PYTHON_VERSION=3.8.5
RUN pyenv install ${PYTHON_VERSION}
RUN pyenv global ${PYTHON_VERSION}
RUN pip install pipenv

WORKDIR /app

# Copy built application
COPY --from=build /app /app

RUN pipenv install --system --deploy --ignore-pipfile

# Start the server by default, this can be overwritten at runtime
EXPOSE 8000
CMD [ "pipenv", "run", "npm", "run", "run-production" ]
