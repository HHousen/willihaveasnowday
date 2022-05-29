![WilliHaveASnowDay Logo](src/assets/img/logo_256.webp)

# Will I Have A Snow Day

> A website that predicts the chance of a snow day automatically by using AI and machine learning.

The AI model is written with [scikit-learn](https://scikit-learn.org/) and [fast.ai](https://docs.fast.ai/), the backend is [flask](http://flask.pocoo.org/) (and gunicorn server for production), and the frontend uses [Materialize.css](https://materializecss.com/).

Website: <https://willihaveasnowday.com/>

## Getting Started

These instructions will get you a copy of the project up and running on your local machine for development and testing purposes. See deployment for notes on how to deploy the project on a live system.

### Prerequisites

* [Python](https://www.python.org/)
* [Pipenv](https://docs.pipenv.org/en/latest/install/#installing-pipenv)
* [Git](https://git-scm.com/)
* [NPM](https://docs.npmjs.com/downloading-and-installing-node-js-and-npm)

### Installation (Development Setup)

```bash
git clone https://github.com/HHousen/willihaveasnowday.git
cd willihaveasnowday
pipenv install
npm install
cp .env.example .env
source .env
npm start
```

## Project Structure

```
.
├── app
│   ├── forms
│   ├── static
│   │   ├── css
│   │   ├── img
│   │   └── js
│   ├── templates
│   │   ├── admin
│   │   ├── components
│   │   ├── email
│   │   └── user
│   ├── toolbox
│   ├── uszipcode
│   └── views
└── src
    ├── assets
    │   └── img
    ├── js
    │   ├── account
    │   ├── contact
    │   ├── form_functions
    │   ├── index
    │   └── scripts
    └── sass
        └── materialize
            └── components
                └── forms
```

## Deployment

```
ENV=production
FLASK_ENV=production
```

Push to Heroku with environment variables set. Run command already located in [Procfile](Procfile).
Or use a different service. Run command is `npm run run-production`.

## Meta

Hayden Housen – [haydenhousen.com](https://haydenhousen.com)

This code is copyright Hayden Housen. You must contact me for permission to reuse these files.

<https://github.com/HHousen>

## Contributing

1. Fork it (<https://github.com/HHousen/willihaveasnowday/fork>)
2. Create your feature branch (`git checkout -b feature/fooBar`)
3. Commit your changes (`git commit -am 'Add some fooBar'`)
4. Push to the branch (`git push origin feature/fooBar`)
5. Create a new Pull Request
