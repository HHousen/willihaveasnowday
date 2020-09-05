exports.files = {
    stylesheets: {
        joinTo: 'css/style.css'
    },
    javascripts: {
        joinTo: {
            'js/scripts.js': /scripts/,
            'js/index.js': /index/,
            'js/account.js': /account/,
        }
    }
};
  
exports.plugins = {
    sass: {
        mode: 'native',
        sourceMapEmbed: true
    },
    postcss: {
        processors: [require('autoprefixer')]
    },
    terser: {
        mangle: true,
        compress: {
            global_defs: {DEBUG: false,},
        },
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