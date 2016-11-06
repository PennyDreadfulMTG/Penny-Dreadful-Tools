window.PD = {}
PD.init = function () {
    $('.fade-repeats').each(PD.fadeRepeats);
    $('.fade-repeats').css('visibility', 'visible').hide().fadeIn('slow');
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
            wins = parseInt(parts[0]);
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
    $('table').tablesorter()
    $('.fade-repeats').bind('sortEnd', PD.fadeRepeats);
};
PD.fadeRepeats = function () {
    var current, previous, differs;
    $(this).find('td').find('*').addBack().removeClass('repeat');
    $(this).find('tr').each(function() {
        current = $(this).find('td').toArray();
        if (current.length > 0 && !differs) {
            differs = new Array(current.length);
            console.log(current.length);
        }
        if (previous) {
            for (i = 0; i < current.length; i++) {
                if ($(current[i]).text().trim() == $(previous[i]).text().trim()) {
                    if ($(current[i]).text().indexOf('⊕') === -1 && $(current[i]).text().indexOf('★') === -1) {
                        $(current[i]).find('*').addBack().addClass('repeat');
                    }
                } else {
                    differs[i] = true;
                }
            }
        }
        previous = current;
    })
    for (var i = 0; i < differs.length; i++) {
        if (!differs[i]) {
            $(this).find('th:nth-child(' + (i + 1) + ')').hide();
            $(this).find('td:nth-child(' + (i + 1) + ')').hide();
        }
    }
};
$(document).ready(function () {
    PD.init();
});
