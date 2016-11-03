window.PD = {}
PD.init = function () {
    $.tablesorter.addParser({
        'id': 'record',
        'is': function(s) {
            return s.match(/^\d+–\d+$/);
        },
        'format': function(s) {
            var parts, wins, losses;
            if (s == '') {
                return '';
            }
            parts = s.split('–');
            wins= parseInt(parts[0]);
            losses = parseInt(parts[1]);
            return ((wins - losses) * 1000 + wins).toString();
        },
        'type': 'numeric'
    });
    $.tablesorter.addParser({
        'id': 'colors',
        'is': function(_s, _table, _td, $td) {
            return $td.find('span.mana').length > 0;
        },
        'format': function(_s, _table, td) {
            var i,
                score = 0,
                symbols = ['_', 'W', 'U', 'B', 'R', 'G'];
            for (i = 0; i < symbols.length; i++) {
                if ($(td).find('span.mana-' + symbols[i]).length > 0) {
                    score += Math.pow(i, 10);
                }
            }
            return score;
        },
        'type': 'numeric'
    });
    $('table').tablesorter();
};
$(document).ready(function () {
    PD.init();
});
