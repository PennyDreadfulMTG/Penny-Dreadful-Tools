/*global Deckbox, $ */
/* Tooltip code originally from https://deckbox.org/help/tooltips and now much hacked around and jQuery dependency introduced. */

// Initialize namespaces.
if (typeof Deckbox === "undefined") Deckbox = {};
Deckbox.ui = Deckbox.ui || {};

/**
 * Main tooltip type.
 */
Deckbox.ui.Tooltip = function(className, type) {
    this.el = document.createElement("div");
    this.el.className = className + " " + type;
    this.type = type;
    this.el.style.display = "none";
    document.body.appendChild(this.el);
    this.tooltips = {};
};

Deckbox.ui.Tooltip.prototype = {
    _padContent: function(content) {
        return "<table><tr><td>" + content + '</td><th style="background-position: right top;"></th></tr><tr>' +
            '<th style="background-position: left bottom;"/><th style="background-position: right bottom;"/></tr></table>';
    },

    showImage: function(posX, posY, image) {
        if (image.complete) {
            this.el.innerHTML = "";
            this.el.appendChild(image);
        } else {
            this.el.innerHTML = "Loading…";
            image.onload = function() {
                var self = Deckbox._.tooltip("image");
                self.el.innerHTML = "";
                image.onload = null;
                self.el.appendChild(image);
                self.move(posX, posY);
            };
        }
        this.el.style.display = "";
        this.move(posX, posY);
    },

    hide: function() {
        this.el.style.display = "none";
    },

    move: function(posX, posY) {
        // The tooltip should be offset to the right so that it's not exactly next to the mouse.
        posX += 15;
        posY -= this.el.offsetHeight / 3;

        // Remeber these for when (if) the register call wants to show the tooltip.
        this.posX = posX;
        this.posY = posY;
        if (this.el.style.display === "none") return;

        var pos = Deckbox._.fitToScreen(posX, posY, this.el);

        this.el.style.top = pos[1] + "px";
        this.el.style.left = pos[0] + "px";
    },

    register: function(url, content) {
        this.tooltips[url].content = content;
        if (this.tooltips[url].el._shown) {
            this.el.style.width = "";
            this.el.innerHTML = this._padContent(content);
            this.el.style.width = (20 + Math.min(330, this.el.childNodes[0].offsetWidth)) + "px";
            this.move(this.posX, this.posY);
        }
    }
};
Deckbox.ui.Tooltip.hide = function() {
    Deckbox._.tooltip("image").hide();
    Deckbox._.tooltip("text").hide();
};


Deckbox._ = {
    onDocumentLoad: function(callback) {
        if (window.addEventListener) {
            window.addEventListener("load", callback, false);
        } else {
            window.attachEvent && window.attachEvent("onload", callback);
        }
    },

    preloadImg: function(link) {
        var img = document.createElement("img");
        img.style.display = "none";
        img.style.width = "1px";
        img.style.height = "1px";
        img.src = "https://deckbox.org/mtg/" + $(link).text().replace(/^[0-9 ]*/, "") + "/tooltip";
        return img;
    },

    pointerX: function(event) {
        var docElement = document.documentElement,
            body = document.body || {
                scrollLeft: 0
            };

        return event.pageX ||
            (event.clientX +
                (docElement.scrollLeft || body.scrollLeft) -
                (docElement.clientLeft || 0));
    },

    pointerY: function(event) {
        var docElement = document.documentElement,
            body = document.body || {
                scrollTop: 0
            };

        return event.pageY ||
            (event.clientY +
                (docElement.scrollTop || body.scrollTop) -
                (docElement.clientTop || 0));
    },

    scrollOffsets: function() {
        return [
            window.pageXOffset || document.documentElement.scrollLeft || document.body.scrollLeft,
            window.pageYOffset || document.documentElement.scrollTop || document.body.scrollTop
        ];
    },

    viewportSize: function() {
        var ua = navigator.userAgent,
            rootElement;
        if (ua.indexOf("AppleWebKit/") > -1 && !document.evaluate) {
            rootElement = document;
        } else if (Object.prototype.toString.call(window.opera) === "[object Opera]" && window.parseFloat(window.opera.version()) < 9.5) {
            rootElement = document.body;
        } else {
            rootElement = document.documentElement;
        }

        /* IE8 in quirks mode returns 0 for these sizes. */
        var size = [rootElement["clientWidth"], rootElement["clientHeight"]];
        if (size[1] === 0) {
            return [document.body["clientWidth"], document.body["clientHeight"]];
        } else {
            return size;
        }
    },

    fitToScreen: function(posX, posY, el) {
        var scroll = Deckbox._.scrollOffsets(),
            viewport = Deckbox._.viewportSize();

        /* decide if wee need to switch sides for the tooltip */
        /* too big for X */
        if ((el.offsetWidth + posX) >= (viewport[0] - 15)) {
            posX = posX - el.offsetWidth - 20;
        }

        /* If it's too high, we move it down. */
        if (posY - scroll[1] < 0) {
            posY += scroll[1] - posY + 5;
        }
        /* If it's too low, we move it up. */
        if (posY + el.offsetHeight - scroll[1] > viewport[1]) {
            posY -= posY + el.offsetHeight + 5 - scroll[1] - viewport[1];
        }

        return [posX, posY];
    },

    addEvent: function(obj, type, fn) {
        if (obj.addEventListener) {
            if (type === "mousewheel") obj.addEventListener("DOMMouseScroll", fn, false);
            obj.addEventListener(type, fn, false);
        } else if (obj.attachEvent) {
            obj["e" + type + fn] = fn;
            obj[type + fn] = function() {
                obj["e" + type + fn](window.event);
            };
            obj.attachEvent("on" + type, obj[type + fn]);
        }
    },

    removeEvent: function(obj, type, fn) {
        if (obj.removeEventListener) {
            if (type === "mousewheel") obj.removeEventListener("DOMMouseScroll", fn, false);
            obj.removeEventListener(type, fn, false);
        } else if (obj.detachEvent) {
            obj.detachEvent("on" + type, obj[type + fn]);
            obj[type + fn] = null;
            obj["e" + type + fn] = null;
        }
    },

    loadJS: function(url) {
        var s = document.createElement("s" + "cript");
        s.setAttribute("type", "text/javascript");
        s.setAttribute("src", url);
        document.getElementsByTagName("head")[0].appendChild(s);
    },

    loadCSS: function(url) {
        var s = document.createElement("link");
        s.type = "text/css";
        s.rel = "stylesheet";
        s.href = url;
        document.getElementsByTagName("head")[0].appendChild(s);
    },

    needsTooltip: function(el) {
        if ($(el).hasClass("card")) return true;
    },

    tooltip: function(which) {
        if (which === "image") return this._iT = this._iT || new Deckbox.ui.Tooltip("deckbox_i_tooltip", "image");
        if (which === "text") return this._tT = this._tT || new Deckbox.ui.Tooltip("deckbox_t_tooltip", "text");
    },

    target: function(event) {
        var target = event.target || event.srcElement || document;
        /* check if target is a textnode (safari) */
        if (target.nodeType === 3) target = target.parentNode;
        return target;
    },

    onmouseover: function(event) {
        var el = Deckbox._.target(event);
        if (Deckbox._.needsTooltip(el)) {
            var no = el.getAttribute("data-nott"),
                url,
                posX = Deckbox._.pointerX(event),
                posY = Deckbox._.pointerY(event);
            if (!no) {
                el._shown = true;
                url = $(el).data("tt");
                if (url) {
                    Deckbox._.showImage(el, url, posX, posY);
                }
            }
        }
    },

    showImage: function(el, url, posX, posY) {
        var img = document.createElement("img");
        url = url.replace(/\?/g, ""); /* Problematic with routes on server. */
        img.src = url;
        img.height = 310;

        setTimeout(function() {
            if (el._shown) Deckbox._.tooltip("image").showImage(posX, posY, img);
        }, 200);
    },

    onmousemove: function(event) {
        var el = Deckbox._.target(event),
            posX = Deckbox._.pointerX(event),
            posY = Deckbox._.pointerY(event);
        if (Deckbox._.needsTooltip(el)) {
            Deckbox._.tooltip("image").move(posX, posY);
        }
    },

    onmouseout: function(event) {
        var el = Deckbox._.target(event);
        if (Deckbox._.needsTooltip(el)) {
            el._shown = false;
            Deckbox._.tooltip("image").hide();
        }
    },

    click: function() {
        Deckbox._.tooltip("image").hide();
    },

    enable: function() {
        Deckbox._.addEvent(document, "mouseover", Deckbox._.onmouseover);
        Deckbox._.addEvent(document, "mousemove", Deckbox._.onmousemove);
        Deckbox._.addEvent(document, "mouseout", Deckbox._.onmouseout);
        Deckbox._.addEvent(document, "click", Deckbox._.click);
    }
};

/**
 * Preload images and CSS for maximum responsiveness even though this does unnecessary work on touch devices.
 */
(function() {
    var protocol = (document.location.protocol === "https:") ? "https:" : "http:";
    Deckbox._.loadCSS(protocol + "//deckbox.org/assets/external/deckbox_tooltip.css");
    /* IE needs more shit */
    if (!!window.attachEvent && !(Object.prototype.toString.call(window.opera) === "[object Opera]")) {
        Deckbox._.loadCSS(protocol + "//deckbox.org/assets/external/deckbox_tooltip_ie.css");
    }

    /* Preload the tooltip images. */
    Deckbox._.onDocumentLoad(function() {
        $(".card").each(function() {
            $(this).data("tt", "https://deckbox.org/mtg/" + $(this).text().replace(/^[0-9 ]*/, "") + "/tooltip");
        });
        var allLinks = document.getElementsByTagName("a");
        for (var i = 0; i < allLinks.length; i++) {
            var link = allLinks[i];
            if (Deckbox._.needsTooltip(link)) {
                document.body.appendChild(Deckbox._.preloadImg(link));
            }
        }
    });
})();
