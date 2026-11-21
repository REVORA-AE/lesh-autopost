# The live 3D mark

`mark.src.js` is the source of `site_src/mark.js`, the spinning question mark on the site.
Rebuild after changing it:

    npm install three@0.170.0 esbuild@0.24.0
    npx esbuild mark.src.js --bundle --minify --format=iife --target=es2019 --outfile=../site_src/mark.js
