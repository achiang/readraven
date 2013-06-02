(function() {
"use strict";
window.APP=window.APP||{Routers:{},Collections:{},Models:{},Views:{}};

APP.Views.Reader = Backbone.View.extend({
    _rendered: false,
    _renderLeftSide: function() {
        this.$el.find('#feed-list').load('/raven/_feedlist/');
    },
    _renderRightSide: function() {
        var view = new APP.Views.FeedItemListView({items: this.items});
        this.$el.find('#strong-side').html(view.render().el);
    },
    addFeed: function(e) {
        e.preventDefault();
        var url = $('#add-feed').val();
        var urlregex = new RegExp(
            "^(http:\/\/|https:\/\/|ftp:\/\/){1}([0-9A-Za-z]+)");
        if (urlregex.test(url)) {
            console.log('adding feed for '+url);
            var feed = new APP.Models.Feed({
                link: url
            });
            feed.save();
            this.feeds.add(feed);
        } else {
            // TODO: handle the error
            console.log('not a url');
        }
        $('#add-feed').val('');
    },
    deleteFeed: function(e) {
        /* TODO: we should really pop up a "confirm"-type box. */
        e.preventDefault();
        var target = $(e.target).parent().parent(),
            feedID = target.attr('data-feedid'),
            feed = this.feeds.where({id: parseInt(feedID, 10)})[0];
        feed.destroy({
            success: function(model, response) {
                target.remove();
            }
        });
    },
    el: '#main',
    events: {
        'click button#add-feed': 'addFeed',
        'click div.delete-feed': 'deleteFeed'
    },
    initialize: function(options) {
        /* Disabled for now.
        this.feeds = new APP.Collections.Feeds();
         */
    },
    render: function() {
        if (this._rendered) { return this; }

        var template = Handlebars.compile($('#index-template').html());
        this.$el.html(template);

        /* Disabled for now.
        this.feeds.fetch({success: this.feeds.onSuccess});
         */
        this._renderLeftSide();

        this._rendered = true;
        return this;
    },
    setFeed: function(id) {
        this.feed = undefined;
        this.items = undefined;
        this.$el.find('#strong-side').empty();

        if (!id) {
            this.items = new APP.Collections.FeedItems();

            this.items.on('reset', function() {
                this._renderRightSide();
            }, this);
            this.items.fetch({reset: true, success: this.items.onSuccess});
        } else {
            /* This motherfucking bullshit right here is because
             * motherfucking Backbone fucking Relational doesn't modify
             * Collection to pull for the Store.
             */
            /* Disabled for now.
            this.feed = this.feeds.where({id: parseInt(id, 10)})[0];
            if (!this.feed) {
                this.feed = APP.Models.Feed.findOrCreate({id: id});
            }
            */

            this.feed = APP.Models.Feed.findOrCreate({id: id});
            this.feed.once('sync', _.bind(function(__) {
                this.items = this.feed.get('items');
                this.items.once('sync', _.bind(function(__) {
                    this._renderRightSide();
                }, this));
                this.feed.fetchRelated('items');
            }, this));
            this.feed.fetch();
        }
    }
});

$.fn.isOnScreen = function(){
    /* Convenience method for checking to see if a node is in the viewport. */
    var win = $(window);

    var viewport = {
        top : win.scrollTop(),
        left : win.scrollLeft()
    };
    viewport.right = viewport.left + win.width();
    /* HACK! We only want the top quarter to trigger the event... */
    viewport.bottom = viewport.top + (win.height() * .25);

    var bounds = this.offset();
    if (bounds === undefined) { return; }

    bounds.right = bounds.left + this.outerWidth();
    bounds.bottom = bounds.top + this.outerHeight();

    return (!(viewport.right < bounds.left || viewport.left > bounds.right ||
              viewport.bottom < bounds.top || viewport.top > bounds.bottom));
};

APP.Views.FeedItemListView = Backbone.View.extend({
    _add: function(item) {
        this._renderItem(item);
        this._loader.show();
    },
    _more: function(e) {
        e.preventDefault();

        if (this.items.hasNext()) {
            this.items.getNext();
        }
        this._loader.hide();
    },
    _remove: function(e) {
        /* TODO: implement this? */
    },
    _renderItem: function(item) {
        var view = new APP.Views.FeedItemView({item: item}),
            container = this.$el.find('#feeditem-container');
        container.append(view.render().el);
    },
    _scrollLast: 0,
    _scroll: function(e) {
        var selected = $('.feeditem.selected'),
            par = null,
            item = null,
            next = null,
            headline = null;
        if (selected.length === 0) {
            par = $('.feeditem').eq(0).parent();
            item = this.items.get(par.attr('data-feeditem'));
            par.find('.feeditem').addClass('selected');
            item.save({'read': true});
        } else {
            par = selected.parent();
            var next_par = null;

            var scrollPosition = $(e.currentTarget).scrollTop();
            if (scrollPosition > this._scrollLast) {
                /* Scroll down */
                next_par = par.next();

                next = next_par.find('.feeditem');
                headline = next.find('h3');
                var current_headline = selected.find('h3');
                if (headline.isOnScreen() && !current_headline.isOnScreen()) {
                    item = this.items.get(next_par.attr('data-feeditem'));
                    item.save({'read': true});

                    selected.removeClass('selected');
                    next.addClass('selected');
                }
            } else if (scrollPosition < this._scrollLast) {
                /* Scroll up */
                next_par = par.prev();
                if (next_par.length === 0) { return; }

                next = next_par.find('.feeditem');
                headline = selected.find('h3');
                if (!headline.isOnScreen() && next.isOnScreen()) {
                    item = this.items.get(next_par.attr('data-feeditem'));
                    item.save({'read': true});

                    selected.removeClass('selected');
                    next.addClass('selected');
                }
            }
            this._scrollLast = scrollPosition;
        }
    },
    initialize: function(options) {
        this.items = options.items;

        this.items.on('add', _.bind(this._add, this));
        this.items.on('remove', _.bind(this._remove, this));
        this.items.on('reset sort', _.bind(this.render, this));
    },
    render: function() {
        $('#strong-side').scroll(_.bind(this._scroll, this));

        var el = this.$el,
            template = Handlebars.compile($('#feed-item-list-template').html());
        el.html(template({}));
        this._loader = el.find('.feeditem-loader');

        el.find('#loader').click(_.bind(this._more, this));

        var container = el.find('#feeditem-container');
        container.children().remove();
        _.each(this.items.models, _.bind(function(item) {
            this._renderItem(item);
        }, this));

        return this;
    }
});

APP.Views.FeedItemView = Backbone.View.extend({
    _render: function() {
        var template = Handlebars.compile($('#feed-item-template').html());
        var context = {
            feed: this.item.get('feed').attributes,
            item: this.item.attributes
        };
        this.$el.html(template(context));
        this.$el.find('a').attr('target', '_blank');
    },
    className: 'row',
    initialize: function(options) {
        this.item = options.item;
        this.$el.attr('data-feeditem', this.item.id);
    },
    render: function() {
        if (this.item.get('title') !== undefined) {
            this._render();
        } else {
            this.item.on('change', function() {
                this._render();
            }, this);
            this.item.fetch();
        }

        return this;
    }
});

}());
