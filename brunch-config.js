exports.files = {
    stylesheets: {
        joinTo: 'css/style.css'
    },
    javascripts: {
        joinTo: 'js/scripts.js'
    }
};
  
exports.plugins = {
    sass: {
        mode: 'native',
        sourceMapEmbed: true
    },
    postcss: {
        processors: [require('autoprefixer')]
    }
};

exports.paths = {
    public: 'app/static/',
    watched: ['src']
}

exports.modules = {
    wrapper: false,
    definition: false
}

exports.npm = {
    enabled: false
}

exports.overrides = {
    production: {
      optimize: true,
      sourceMaps: false
    }
  }