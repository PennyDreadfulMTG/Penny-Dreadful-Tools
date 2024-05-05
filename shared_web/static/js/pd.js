/*global PD:true, Deckbox:false, moment:false, $, Tipped, Chart, ChartDataLabels, Bloodhound */
/* eslint-disable max-lines */
window.PD = {};

PD.init = function() {
    PD.initDismiss();
    PD.initMenu();
    PD.initDoubleReportCheck();
    PD.initAchievements();
    PD.initTables();
    PD.initDetails();
    PD.initTooltips();
    PD.initTypeahead();
    PD.initSearchShortcut();
    PD.initReassign();
    PD.initRuleForms();
    $("input[type=file]").on("change", PD.loadDeck).on("change", PD.toggleDrawDropdown);
    $(".bugtable").trigger("sorton", [
        [
            [2, 0],
            [0, 0]
        ]
    ]);
    $(".toggle-illegal").on("change", PD.toggleIllegalCards);
    PD.localizeTimes();
    PD.initSignupDeckChooser();
    PD.initPersonalization();
    PD.renderCharts();
};

PD.initDismiss = function() {
    $(".dismiss").click(function() {
        $(this).closest(".intro-container").hide();
        $.post("/api/intro/"); // Fire and forget request to set cookie to remember dismissal of intro box and not show it again.
        return false;
    });
};

PD.initMenu = function() {
    $(".has-submenu").hoverIntent({
        over: PD.onDropdownHover,
        out: PD.onDropdownLeave,
        interval: 50,
        timeout: 250
    });
};

PD.onDropdownHover = function() {
    if (window.matchMedia("only screen and (min-width: 641px)").matches) {
        $(this).addClass("hovering");
        $(this).find(".submenu-container").slideDown("fast");
    }
};

PD.onDropdownLeave = function() {
    if (window.matchMedia("only screen and (min-width: 641px)").matches) {
        $(this).removeClass("hovering");
        $(this).find(".submenu-container").slideUp("fast");
    }
};

PD.initAchievements = function() {
    $(".has-more-info").click(PD.onMoreInfoClick);
};

PD.onMoreInfoClick = function() {
    $(this).siblings(".more-info").slideToggle();
};

PD.initTables = function() {
    var selector = "main table";
    var noTablesorter = "table.live";

    $.tablesorter.addParser({
        "id": "record",
        "is": function(s) {
            return s.match(/^\d+–\d+(–\d+)?$/);
        },
        "format": function(s) {
            var parts, wins, losses;
            if (s === "") {
                return "";
            }
            parts = s.split("–");
            wins = parseInt(parts[0], 10);
            losses = parseInt(parts[1], 10);
            return ((wins - losses) * 1000 + wins).toString();
        },
        "type": "numeric"
    });
    $.tablesorter.addParser({
        "id": "colors",
        "is": function(_s, _table, _td, $td) {
            return $td.find("span.mana").length > 0;
        },
        "format": function(_s, _table, td) {
            var i,
                score = 0,
                symbols = ["_", "W", "U", "B", "R", "G"];
            for (i = 0; i < symbols.length; i++) {
                if ($(td).find("span.mana-" + symbols[i]).length > 0) {
                    score += Math.pow(i, 10);
                }
            }
            return score;
        },
        "type": "numeric"
    });
    PD.bugCategories = ["Game Breaking", "Avoidable Game Breaking", "Advantageous", "Disadvantageous", "Graphical", "Non-Functional ability", "Unclassified"];
    $.tablesorter.addParser({
        "id": "bugseverity",
        "is": function(s) {
            return PD.bugCategories.indexOf(s) > -1;
        },
        "format": function(s) {
            return PD.bugCategories.indexOf(s);
        },
        "type": "numeric"
    });
    $.tablesorter.addParser({
        "id": "archetype",
        is: function(_s, _table, _td, $td) {
            return $td.hasClass("initial");
        },
        "format": function(s, table, td) {
            return $(td).data("sort");
        },
        "type": "numeric"
    });
    /* Give archetype columns the classes primary and secondary so that we can nest when sorted by first column but not otherwise. */
    $("table.archetypes").tablesorter({
        "sortList": [
            [0, 0]
        ],
        "widgets": ["columns"],
        "widgetOptions": {
            "columns": ["primary", "secondary"]
        }
    });
    $(selector).not(noTablesorter).tablesorter({});
};

PD.initDetails = function() {
    $(".details").siblings("p.question").click(function() {
        $(this).siblings(".details").toggle();
        return false;
    });
};

// Disable tooltips on touch devices where they are awkward but enable on others where they are useful.
PD.initTooltips = function() {
    $("body").on("touchstart", function() {
        $("body").off();
    });
    $("body").on("mouseover", function() {
        if (typeof Deckbox !== "undefined") {
            Deckbox._.enable();
        }
        Tipped.delegate("main [title]", {
            "showDelay": 500,
            "size": "large",
            maxWidth: "200"
        });
        $("body").off();
    });
};

PD.initTypeahead = function() {
    var corpus = new Bloodhound({
        datumTokenizer: Bloodhound.tokenizers.obj.whitespace("name"),
        queryTokenizer: Bloodhound.tokenizers.whitespace,
        remote: {
            "url": "/api/search/?q={q}",
            "wildcard": "{q}"
        }
    });
    var options = {
        "autoselect": true,
        "highlight": true,
        "hint": true
    };
    var dataSource = {
        "display": "name",
        "limit": 10,
        "source": corpus,
        "templates": {
            "empty": function() { return '<div class="tt-suggestion">No results found</div>'; },
            "suggestion": function (o) { return "<div><strong>{{name}}</strong> – {{type}}</div>".replace("{{name}}", o.name).replace("{{type}}", o.type); }
        }
    };
    $(".typeahead").typeahead(options, dataSource);
    $(".typeahead").bind("typeahead:select", function(event, suggestion) {
        window.location.href = suggestion.url;
    });
};

PD.initSearchShortcut = function() {
    $(document).keypress(function(e) {
        if (!$(e.target).is(":input") && String.fromCharCode(e.which) === "/") {
            $(".typeahead").val("");
            $(".typeahead").focus();
            e.preventDefault();
        }
    });
};

PD.initReassign = function() {
    $(".reassign").click(function() {
        $(this).hide();
        $.post("/api/archetype/reassign", {
            "deck_id": $(this).data("deck_id"),
            "archetype_id": $(this).data("rule_archetype_id")
        }, PD.afterReassign);
        return false;
    });
};

PD.afterReassign = function(data) {
    $('tr:has(a[data-deck_id="' + data.deck_id + '"])').hide();
};

PD.initRuleForms = function() {
    $(".rule-form").submit(function() {
        var form = $(this);
        var url = form.attr("action");
        $.ajax({
            type: "POST",
            url,
            data: form.serialize(), // serializes the form's elements.
            success: PD.afterRuleUpdate,
            error: PD.ruleUpdateFailure
        });
        return false;
    });
};

PD.afterRuleUpdate = function(data) {
    if (data.success) {
        window.location = location.href; // make sure it's a GET refresh and not a duplicate of a previous POST
    } else {
        alert(data.msg); // eslint-disable-line no-alert
    }
};

PD.ruleUpdateFailure = function(_xhr, textStatus, errorThrown) {
    alert(textStatus + " " + errorThrown); // eslint-disable-line no-alert
};

PD.loadDeck = function() {
    var file = this.files[0],
        reader = new FileReader();
    reader.onload = function(event) {
        $("textarea").val(event.target.result);
    };
    reader.readAsText(file);
};

PD.initDoubleReportCheck = function () {
    $(".content-report form button[type=submit]").click(function () {
        const $form = $(".content-report form");
        const opponents = $form.data("opponents");
        const $selected = $form.find("[name=opponent] option:selected");
        const opponent = $selected.text();
        const opponentDeckId = $selected.val();
        if (opponents[opponent] && opponents[opponent].toString() !== opponentDeckId.toString()) {
            return confirm("A match against " + opponent + " on another deck has already been reported. Did you play them again?");  // eslint-disable-line no-alert
        }
        return true;
    });
};

PD.toggleDrawDropdown = function() {
    var canDraw = false;
    $(document).find(".deckselect").each(function(_, select) {
        canDraw = canDraw || select.selectedOptions[0].classList.contains("deck-can-draw");
    });
    if (canDraw) {
        $(".draw-report").css("visibility", "visible");
    } else {
        $(".draw-report").css("visibility", "hidden");
        $("#draws").val(0);
    }
    return canDraw;
};

PD.toggleIllegalCards = function() {
    // Fix the width of the table columns so that it does not "jump" when rows are added or removed.
    $(".bugtable tr td").each(function() {
        $(this).css({
            "width": $(this).width() + "px"
        });
    });
    $("tr").find(".illegal").closest("tr").toggle(!this.checked);
};

PD.localizeTimes = function() {
    PD.localizeTimeElements();
    PD.hideRepetitionInCalendar();
};

PD.localizeTimeElements = function() {
    $("time").each(function() {
        var t = moment($(this).attr("datetime")),
            format = $(this).data("format"),
            tz = moment.tz.guess(),
            s = t.tz(tz).format(format);
        $(this).html(s).show();
    });
};

PD.hideRepetitionInCalendar = function() {
    PD.hideRepetition(".calendar time.month");
    PD.hideRepetition(".calendar time.day");
};

PD.hideRepetition = function(selector) {
    var v;
    $(selector).each(function() {
        if ($(this).html() === v) {
            $(this).html("");
        } else {
            v = $(this).html();
        }
    });
};

PD.getUrlParams = function() {
    var vars = [],
        hash, i,
        hashes = window.location.href.slice(window.location.href.indexOf("?") + 1).split("&");
    for (i = 0; i < hashes.length; i++) {
        hash = hashes[i].split("=");
        vars.push(hash[0]);
        vars[hash[0]] = hash[1];
    }
    return vars;
};
PD.getUrlParam = function(name) {
    return PD.getUrlParams()[name];
};

PD.initSignupDeckChooser = function() {
    $("#signup_recent_decks").on("change", function() {
        var data = JSON.parse($("option:selected", this).attr("data"));
        $("#name").val(data.name);
        var textarea = $("#decklist");
        var buffer = data.main.join("\n") + "\n";
        if (data.sb.length > 0) {
            buffer += "\nSideboard:\n" + data.sb.join("\n");
        }
        textarea.val(buffer);
    });
};

PD.initPersonalization = function() {
    $.get("/api/status", function(data) {
        var text = "";
        if (data.discord_id) {
            text += "You are logged in";
            if (data.mtgo_username !== null) {
                text += " as <a href=\"/people/" + PD.htmlEscape(data.mtgo_username) + "\">" + PD.htmlEscape(data.mtgo_username) + "</a>";
            } else {
                text += " <span class=\"division\"></span> <a href=\"/link/\">Link</a> your Magic Online account";
            }
            if (data.deck) {
                text += " <span class=\"division\"></span> " + data.deck.wins + "–" + data.deck.losses + " with <a href=\"" + PD.htmlEscape(data.deck.url) + "\">" + PD.htmlEscape(data.deck.name) + "</a> <span class=\"division\"></span> <a href=\"/report/\">Report</a> <span class=\"division\"></span> <a href=\"/retire/\">Retire</a>";
                if (data.league_end) {
                    text += "<span class=\"division\"></span> <a href=\"/league/current/\">Current league</a> ends in " + data.league_end;
                }
            } else if (data.mtgo_username !== null) {
                text += " <span class=\"division\"></span> You do not have an active league run — <a href=\"/signup/\">Sign Up</a>";
            }
            text += " <span class=\"division\"></span> <a href=\"/logout/\">Log Out</a>";
        } else {
            text += "<a href=\"/authenticate/?target=" + window.location.href + "\">Log In</a>";
        }
        $(".status-bar").html("<p>" + text + "</p>");
        if (data.admin) {
            $(".admin").show();
            PD.initPersonNotes();
        }
        if (data.demimod) {
            $(".demimod").show();
        }
        if ((data.admin || data.demimod) && (data.archetypes_to_tag > 0)) {
            $(".edit_archetypes").children()[0].text = data.archetypes_to_tag;
        }
        if (!data.hide_intro && !PD.getUrlParam("hide_intro")) {
            $(".intro-container").show();
        }
    });
};

PD.initPersonNotes = function() {
    var i, personId = $(".person-notes").data("person_id");
    // Only do the work if we're on a page that should show the notes.
    if (personId) {
        $.get("/api/admin/people/" + personId + "/notes", function(data) {
            if (data.notes.length > 0) {
                let s = "<article>";
                for (i = 0; i < data.notes.length; i++) {
                    s += '<p><span class="subtitle">' + data.notes[i].display_date + "</span> " + data.notes[i].note + "</p>";
                }
                s += "</article>";
                $(".person-notes").html(s);
            } else {
                $(".person-notes").html("<p>None</p>");
            }
        });
    }
};

PD.renderCharts = function() {
    Chart.register(ChartDataLabels);
    Chart.defaults.font.family = $("body").css("font-family");
    if ($("td").length > 0) {
        const fontSize = parseInt($("td").css("font-size"), 10);
        Chart.defaults.font.size = fontSize;
        Chart.defaults.plugins.datalabels.font.size = fontSize;
    }
    Chart.defaults.plugins.legend.display = false;
    Chart.defaults.plugins.tooltip.enabled = false;
    Chart.defaults.plugins.datalabels.formatter = function (value) {
        return value || "";
    };
    Chart.defaults.plugins.datalabels.anchor = "end";
    Chart.defaults.plugins.datalabels.align = "end";
    Chart.defaults.plugins.tooltip.displayColors = false;
    Chart.defaults.plugins.colors.enabled = false;
    Chart.defaults.color = "#502828";
    $(".chart").each(function() {
        var type = $(this).data("type"),
            labels = $(this).data("labels"),
            series = $(this).data("series"),
            options = $(this).data("options"),
            ctx = this.getContext("2d");
        // eslint-disable-next-line new-cap
        // eslint-disable-next-line no-new
        new Chart(ctx, {
            type,
            "data": {
                labels,
                datasets: [{ data: series, backgroundColor: "#f9d0a9" }]
            },
            options
        });
    });
};

PD.htmlEscape = function(s) {
    return $("<div>").text(s).html();
};

$(document).ready(function() {
    PD.init();
});


// Shift-click checkboxes behavior.
// Inlining https://raw.githubusercontent.com/rmariuzzo/checkboxes.js/master/src/jquery.checkboxes.js because it's not very big and there's no CDN version.
/* eslint-disable */
(($) => {

    /**
     * The Checkboxes class object.
     */
    class Checkboxes {

        /**
         * Create a new checkbox context.
         *
         * @param {Object} context DOM context.
         */
        constructor(context) {
            this.$context = context;
        }

        /**
         * Check all checkboxes in context.
         */
        check() {
            this.$context.find(':checkbox')
                .filter(':not(:disabled)')
                .filter(':visible')
                .prop('checked', true)
                .trigger('change');
        }

        /**
         * Uncheck all checkboxes in context.
         */
        uncheck() {
            this.$context.find(':checkbox:visible')
                .filter(':not(:disabled)')
                .prop('checked', false)
                .trigger('change');
        }

        /**
         * Toggle the state of all checkboxes in context.
         */
        toggle() {
            this.$context.find(':checkbox:visible')
                .filter(':not(:disabled)')
                .each((i, element) => {
                    let $checkbox = $(element);
                    $checkbox.prop('checked', !$checkbox.is(':checked'));
                })
                .trigger('change');
        }

        /**
         * Set the maximum number of checkboxes that can be checked.
         *
         * @param {Number} max The maximum number of checkbox allowed to be checked.
         */
        max(max) {
            if (max > 0) {
                // Enable max.
                let instance = this;
                this.$context.on('click.checkboxes.max', ':checkbox', () => {
                    if (instance.$context.find(':checked').length === max) {
                        instance.$context.find(':checkbox:not(:checked)').prop('disabled', true);
                    } else {
                        instance.$context.find(':checkbox:not(:checked)').prop('disabled', false);
                    }
                });
            } else {
                // Disable max.
                this.$context.off('click.checkboxes.max');
            }
        }

        /**
         * Enable or disable range selection.
         *
         * @param {Boolean} enable Indicate is range selection has to be enabled.
         */
        range(enable) {
            if (enable) {
                let instance = this;

                this.$context.on('click.checkboxes.range', ':checkbox', (event) => {
                    let $checkbox = $(event.target);

                    if (event.shiftKey && instance.$last) {
                        let $checkboxes = instance.$context.find(':checkbox:visible');
                        let from = $checkboxes.index(instance.$last);
                        let to = $checkboxes.index($checkbox);
                        let start = Math.min(from, to);
                        let end = Math.max(from, to) + 1;

                        $checkboxes.slice(start, end)
                            .filter(':not(:disabled)')
                            .prop('checked', $checkbox.prop('checked'))
                            .trigger('change');
                    }
                    instance.$last = $checkbox;
                });
            } else {
                this.$context.off('click.checkboxes.range');
            }
        }
    }

    /* Checkboxes jQuery plugin. */

    // Keep old Checkboxes jQuery plugin, if any, to no override it.
    let old = $.fn.checkboxes;

    /**
     * Checkboxes jQuery plugin.
     *
     * @param {String} method Method to invoke.
     *
     * @return {Object} jQuery object.
     */
    $.fn.checkboxes = function (method) {
        // Get extra arguments as method arguments.
        let args = Array.prototype.slice.call(arguments, 1);

        return this.each((i, element) => {
            let $this = $(element);

            // Check if we already have an instance.
            let instance = $this.data('checkboxes');
            if (!instance) {
                $this.data('checkboxes', (instance = new Checkboxes($this)));
            }

            // Check if we need to invoke a public method.
            if (typeof method === 'string' && instance[method]) {
                instance[method].apply(instance, args);
            }
        });
    };

    // Store a constructor reference.
    $.fn.checkboxes.Constructor = Checkboxes;

    /* Checkboxes jQuery no conflict. */

    /**
     * No conflictive Checkboxes jQuery plugin.
     */
    $.fn.checkboxes.noConflict = function () {
        $.fn.checkboxes = old;
        return this;
    };

    /* Checkboxes data-api. */

    /**
     * Handle data-api click.
     *
     * @param {Object} event Click event.
     */
    var dataApiClickHandler = (event) => {
        var el = $(event.target);
        var href = el.attr('href');
        var $context = $(el.data('context') || (href && href.replace(/.*(?=#[^\s]+$)/, '')));
        var action = el.data('action');

        if ($context && action) {
            if (!el.is(':checkbox')) {
                event.preventDefault();
            }
            $context.checkboxes(action);
        }
    };

    /**
     * Handle data-api DOM ready.
     */
    var dataApiDomReadyHandler = () => {
        $('[data-toggle^=checkboxes]').each(function () {
            let el = $(this);
            let actions = el.data();
            delete actions.toggle;
            for (let action in actions) {
                el.checkboxes(action, actions[action]);
            }
        });
    };

    // Register data-api listeners.
    $(document).on('click.checkboxes.data-api', '[data-toggle^=checkboxes]', dataApiClickHandler);
    $(dataApiDomReadyHandler);

})(window.jQuery);
