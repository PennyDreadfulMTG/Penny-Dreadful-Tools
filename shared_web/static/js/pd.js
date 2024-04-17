/*global PD:true, Deckbox:false, moment:false, $, Tipped, Chart, Bloodhound */
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
    PD.filter.init();
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
    $(".content-report form button[type=submit]").click(function (event) {
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
                text += " <span class=\"division\"></span> " + data.deck.wins + "–" + data.deck.losses + " with <a href=\"" + PD.htmlEscape(data.deck.url) + "\">" + PD.htmlEscape(data.deck.name) + "</a> <span class=\"division\"></span> <a href=\"/retire/\">Retire</a>";
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
    Chart.defaults.font.family = $("body").css("font-family");
    if ($("td").length > 0) {
        Chart.defaults.font.size = parseInt($("td").css("font-size"), 10);
    }
    Chart.defaults.plugins.legend.display = false;
    Chart.defaults.plugins.title.display = false;
    Chart.defaults.plugins.tooltip.displayColors = false;
    Chart.defaults.scale.ticks.beginAtZero = true;
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
                datasets: [{ data: series }]
            },
            options
        });
    });
};

PD.htmlEscape = function(s) {
    return $("<div>").text(s).html();
};

PD.filter = {};

PD.filter.init = function() {

    // if there are no filter-forms on the page, don't try to set anything up
    if ($(".scryfall-filter-form").length === 0) {
        return false;
    }

    $(".toggle-filters-button").click(PD.filter.toggleDisplayFilter);

    // Apply the filter with the initial value of the form
    // The initial value is recieved by the template from the backend
    const initialValue = $(".scryfall-filter-input").val();
    if (initialValue) {
        PD.filter.toggleDisplayFilter();
        PD.filter.scryfallFilter(initialValue);
    }
    // set up the Event handlers for the form
    $(".scryfall-filter-form").submit(function() {
        PD.filter.scryfallFilter($(".scryfall-filter-input").val());
        return false;
    });
    $(".scryfall-filter-reset").click(PD.filter.reset);

    $(".interestingness-filter-radio").change(function() {
        if (this.checked) {
            PD.filter.applyInterestingness(this.value);
        }
    });

    window.onpopstate = function(event) {
        if (event && event.state) {
            if (event.state["cardNames"] !== null) {
                PD.filter.applyCardNames(event.state["cardNames"]);
            } else {
                $(".cardrow").removeClass("hidden-by-scryfall-filter");
            }
            PD.filter.showErrorsAndWarnings(event.state);
            $(".scryfall-filter-input").val(event.state.query);
        } else {
            PD.filter.reset();
            PD.filter.clearErrorsAndWarnings();
            $(".scryfall-filter-input").val("");
        }
    };
};

PD.filter.applyCardNames = function(cardNames) {
    $(".cardrow").each(function() {
        const jqEle = $(this);
        if (cardNames.indexOf(this.dataset.cardname) === -1) {
            jqEle.addClass("hidden-by-scryfall-filter");
        } else {
            jqEle.removeClass("hidden-by-scryfall-filter");
        }
    });
    PD.filter.updateCardCounts();
};

PD.filter.applyInterestingness = function(interestingness) {
    $(".cardrow").each(function() {
        const jqEle = $(this);
        if (interestingness !== "all" && !jqEle.find("a").hasClass("interestingness-" + interestingness)) {
            jqEle.addClass("hidden-by-interestingness-filter");
        } else {
            jqEle.removeClass("hidden-by-interestingness-filter");
        }
    });
    PD.filter.updateCardCounts();
};

// input url returns a promise to {success: true/false, cardNames: [...], error message: {...}}
PD.filter.retrieveAllCards = function(url) {
    const succeed = function(blob) {
        const cards = blob.data.map((x) => x["name"]);
        if (blob["has_more"]) {
            return PD.filter.retrieveAllCards(blob["next_page"]).then(function(newBlob) {
                // Simplifying assumption: if the first page didn't produce scryfall-level errors, neither will the later ones
                // and warnings are the same on all pages
                return {
                    success: true,
                    cardNames: cards.concat(newBlob["cardNames"]),
                    warnings: newBlob["warnings"]
                };
            });
        } else {
            return {
                success: true,
                cardNames: cards,
                warnings: blob["warnings"]
            };
        }
    };

    const fail = function(jqXHR) {
        // we may have failed via a scryfall error, or via a connection error
        if (jqXHR.status === 400 && "responseJSON" in jqXHR) {
            // Scryfall gave us a Bad Request - there were issues with the query
            return {
                success: false,
                details: jqXHR.responseJSON.details,
                warnings: jqXHR.responseJSON.warnings
            };
        } else if (jqXHR.status === 404 && "responseJSON" in jqXHR) {
            // Scryfall returned no cards - that's not a fail, we just display nothing
            // Since this is not a true failure, return a resolved Deffered object
            return $.Deferred().resolve({ // eslint-disable-line new-cap
                success: true,
                cardNames: [],
                warnings: jqXHR.responseJSON.warnings
            });
        } else {
            // We had a 5xx or some other error we don't handle
            return {
                success: false,
                details: "Error connecting to Scryfall",
                warnings: []
            };
        }
    };
    return $.getJSON(url).then(succeed, fail);
};

PD.filter.disableForm = function() {
    $(".scryfall-filter-submit").attr("disabled", "disabled").text("Loading…");
    $(".scryfall-filter-reset").attr("disabled", "disabled").text("Loading…");
    $(".scryfall-filter-form").off("submit").submit(function() {
        return false;
    });
};

PD.filter.enableForm = function() {
    $(".scryfall-filter-submit").removeAttr("disabled").text("Search");
    $(".scryfall-filter-reset").removeAttr("disabled").text("Reset");
    $(".scryfall-filter-form").off("submit").submit(function() {
        PD.filter.scryfallFilter($(".scryfall-filter-input").val());
        return false;
    });
};

PD.filter.toggleDisplayFilter = function() {
    $(".filters-container").slideToggle(200);
    if ($(".toggle-filters-button").text() === "Show filters") {
        $(".toggle-filters-button").text("Hide filters");
    } else {
        $(".toggle-filters-button").text("Show filters");
    }
};

PD.filter.scryfallFilter = function(query) {
    if (query === "") {
        PD.filter.reset();
        return;
    }

    PD.filter.disableForm();
    PD.filter.clearErrorsAndWarnings();

    let url;
    if ("optimize" in $(".scryfall-filter-input").data()) {
        const fasterQuery = "f:pd (" + query + ")";
        url = "https://api.scryfall.com/cards/search?q=" + encodeURIComponent(fasterQuery);
    } else {
        url = "https://api.scryfall.com/cards/search?q=" + encodeURIComponent(query);
    }

    PD.filter.retrieveAllCards(url)
        .done(function(o) {
            const cardNames = o["cardNames"];
            PD.filter.applyCardNames(cardNames);
            history.pushState({
                cardNames,
                warnings: o["warnings"],
                query
            }, "", "?fq=" + query);
            PD.filter.showErrorsAndWarnings(o);
        })
        .fail(PD.filter.showErrorsAndWarnings)
        .always(PD.filter.enableForm);
};

PD.filter.reset = function() {
    $(".cardrow").removeClass("hidden-by-scryfall-filter");
    $(".scryfall-filter-input").val("");
    PD.filter.clearErrorsAndWarnings();
    history.pushState({
        cardNames: null,
        warnings: [],
        query: ""
    }, "", "?fq=");
    PD.filter.updateCardCounts();
    return false;
};

PD.filter.showErrorsAndWarnings = function(o) {
    const p = $(".errors-and-warnings");
    p.empty();
    if ("details" in o) {
        const error = document.createElement("li");
        error.innerText = "Error (query failed) - " + o["details"];
        p.append(error);
    }
    if ("warnings" in o && typeof o["warnings"] !== "undefined") {
        for (let i = 0; i < o["warnings"].length; i++) {
            const warning = document.createElement("li");
            warning.innerText = "Warning: " + o["warnings"][i];
            p.append(warning);
        }
    }
    p.show();
};

PD.filter.clearErrorsAndWarnings = function() {
    $(".errors-and-warnings").empty().hide();
};

PD.filter.updateCardCounts = function() {
    $("span.total").parent().parent().each(function() {
        const l = $(this).find(".cardrow").filter(":visible").length;
        $(this).find("span.total").text(l);
    });
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
