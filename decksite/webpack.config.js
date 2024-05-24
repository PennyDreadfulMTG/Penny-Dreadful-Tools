/* eslint-disable */
module.exports = (env, argv) => {
    const isProduction = argv.mode === 'production';

    return {
        entry: [
            __dirname + "/../shared_web/static/js/cardtable.jsx",
            __dirname + "/../shared_web/static/js/decktable.jsx",
            __dirname + "/../shared_web/static/js/headtoheadtable.jsx",
            __dirname + "/../shared_web/static/js/leaderboardtable.jsx",
            __dirname + "/../shared_web/static/js/matchtable.jsx",
            __dirname + "/../shared_web/static/js/metagamegrid.jsx",
            __dirname + "/../shared_web/static/js/persontable.jsx",
            __dirname + "/../shared_web/static/js/rotationtable.jsx",
        ],
        output: {
            path: __dirname + "/../shared_web/static/dist",
            filename: "bundle.js"
        },
        resolve: {
            extensions: [".js", ".jsx", ".css"]
        },
        module: {
            rules: [{
                test: /\.jsx?/,
                exclude: /node_modules/,
                use: "babel-loader"
            }, {
                test: /\.css$/,
                exclude: /node_modules/,
                use: [{
                    loader: 'style-loader'
                }, {
                    loader: 'css-loader'
                }]
            }]
        },
        devtool: isProduction ? false : 'source-map'
    }
};
