window.PD = {}
PD.init = function () {
    $('.fade-repeats').each(PD.fadeRepeats);
    $('.fade-repeats').css('visibility', 'visible').hide().fadeIn('slow');
    $.tablesorter.addParser({
        'id': 'record',
        'is': function(s) {
            return s.match(/^\d+–\d+(–\d+)?$/);
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
    $('input[type=file]').on('change', PD.loadDeck);
};
PD.fadeRepeats = function () {
    var current, previous;
    $(this).find('td').find('*').addBack().removeClass('repeat');
    $(this).find('tr').each(function() {
        current = $(this).find('td').toArray();
        if (previous) {
            for (i = 0; i < current.length; i++) {
                if ($(current[i]).text().trim() == $(previous[i]).text().trim() && $(current[i]).html().indexOf('mana-') === -1) {
                    if ($(current[i]).text().indexOf('⊕') === -1 && $(current[i]).text().indexOf('★') === -1) {
                        $(current[i]).find('*').addBack().addClass('repeat');
                    }
                }
            }
        }
        previous = current;
    })
};
PD.loadDeck = function () {
    var file = this.files[0],
        reader = new FileReader();
    reader.onload = function (e) {
        $('textarea').val(e.target.result);
    };
    reader.readAsText(file);
}
$(document).ready(function () {
    PD.init();
});
