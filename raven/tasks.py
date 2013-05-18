from datetime import datetime, timedelta
import os
import zipfile

from django.core.exceptions import ObjectDoesNotExist

from celery.task import Task, PeriodicTask
from libgreader import ClientAuthMethod, OAuth2Method, GoogleReader
import json
import opml

from raven.models import Feed, FeedItem, UserFeedItem


class FakeEntry(object):
    def __init__(self, item):
        self.read = False
        self.starred = False
        self.tags = []

        self.id = item['id']
        self.title = item['title']
        self.url = item['url']
        self.content = item['content']
        self.time = item['time']

def _new_user_item(user, feed, entry):
    try:
        item = FeedItem.objects.get(reader_guid=entry.id)
    except ObjectDoesNotExist:
        item = FeedItem()
        item.feed = feed
        item.title = entry.title
        item.link = entry.url
        item.description = entry.content

        item.atom_id = ''
        item.reader_guid = entry.id
        item.published = datetime.utcfromtimestamp(entry.time)
        item.guid = item.calculate_guid()
        item.save()

    try:
        user_item = item.userfeeditem(user)
    except ObjectDoesNotExist:
        # Nasty. The above only works if a user is actually
        # subscribed to a feed. However, it can be the case
        # where we're trying to import Google Reader, and we're
        # processing items that have been shared with us. In
        # this case, we probably won't be subscribed to the
        # feed, and more, we probably don't want to subscribe to
        # the feed. So manually create a UserFeedItem so the
        # Item can be accessed by the User. We can pull it out
        # of the db later by searching for the 'shared-with-you'
        # tag.
        user_item = UserFeedItem()
        user_item.item = item
        user_item.user = user
        user_item.feed = feed
        user_item.save()

    user_item.read = entry.read
    user_item.starred = entry.starred
    for t in entry.tags:
        user_item.tags.add(t)
    user_item.save()

    return user_item

class UpdateFeedTask(PeriodicTask):
    '''A task for updating a set of feeds.'''

    SLICE_SIZE = 100
    run_every = timedelta(seconds=60*5)

    def run(self, feeds=[]):
        if len(feeds) is 0:
            age = datetime.now() - timedelta(minutes=30)
            feeds = Feed.objects.filter(last_fetched__lt=age)[:self.SLICE_SIZE]

        for feed in feeds:
            feed.update()
            feed.last_fetched = datetime.utcnow()
            feed.save()


class ImportOPMLTask(Task):
    '''A task for importing feeds from OPML files.'''

    def _import_subscriptions(self):
        name = os.path.join(
            os.path.splitext(os.path.basename(self.filename))[0],
            'Reader', 'subscriptions.xml')
        try:
            subscriptions = opml.from_string(self.z.open(name).read())
        except KeyError:
            return False

        for sub in subscriptions:
            if hasattr(sub, 'type'):
                title = sub.title
                link = sub.xmlUrl
                site = sub.htmlUrl
                Feed.create_and_subscribe(title, link, site, self.user)
            else:
                # In this case, it's a 'group' of feeds.
                folder = sub
                for sub in folder:
                    title = sub.title
                    link = sub.xmlUrl
                    site = sub.htmlUrl
                    feed = Feed.create_and_subscribe(title, link, site, self.user)

                    userfeed = feed.userfeed(self.user)
                    userfeed.tags.add(folder.title)
        return True

    def _import_starred(self):
        name = os.path.join(
            os.path.splitext(os.path.basename(self.filename))[0],
            'Reader', 'starred.json')
        try:
            starred = json.loads(self.z.open(name).read(), strict=False)
        except KeyError:
            return False

        try:
            # This is like, weak sauce verification, hoping that we're
            # not about to get bogus data. Still, a carefully crafted
            # attack file could make it past this check.
            id = starred['id']
            if not id.endswith('starred'):
                return False
        except KeyError:
            return False

        for i in starred['items']:
            title = i['origin']['title']
            site = i['origin']['htmlUrl']
            link = i['origin']['streamId']
            if link.startswith('feed/'):
                link = link.replace('feed/', '', 1)
            # These are some weird bullshit links created by google
            # reader. Try and discover a real link instead.
            elif link.startswith('user/'):
                maybe = Feed.autodiscover(site)
                if maybe:
                    link = maybe

            feed = Feed.create_raw(title, link, site)

            item = {}
            item['id'] = i['id']
            item['title'] = i['title']
            item['url'] = i.get('canonical', i.get('alternate', ''))[0]['href']
            try:
                item['content'] = i['content']['content']
            except KeyError:
                try:
                    item['content'] = i['summary']['content']
                except KeyError:
                    # No idea if this is even possible, we should squawk
                    item['content'] = ''
            item['time'] = i['published']
            entry = FakeEntry(item)

            for c in i.get('categories', []):
                if c.startswith('user/') and c.endswith('/read'):
                    entry.read = True
                elif c.startswith('user/') and c.endswith('/starred'):
                    entry.starred = True
                elif c.startswith('user/') and ('label' in c):
                    tag = c.split('/')[-1]
                    entry.tags.append(tag)

            user_item = _new_user_item(self.user, feed, entry)
            user_item.tags.add('imported')
            user_item.save()

    def run(self, user, filename, *args, **kwargs):
        if zipfile.is_zipfile(filename):
            with zipfile.ZipFile(filename, 'r') as z:
                self.z = z
                self.user = user
                self.filename = filename

                did_sub = self._import_subscriptions()
                did_star = self._import_starred()
            return did_sub
        else:
            return False


class SyncFromReaderAPITask(Task):
    '''A task for sync'ing data from a Google Reader-compatible API.'''

    def run(self, user, loadLimit, *args, **kwargs):
        # user.credential should always be valid when doing oauth2
        if user.credential:
            credential = user.credential
            auth = OAuth2Method(credential.client_id, credential.client_secret)
            auth.authFromAccessToken(credential.access_token)
            auth.setActionToken()
        # username/password auth method, should only be used by our tests
        elif len(args) == 2:
            auth = ClientAuthMethod(args[0], args[1])

        reader = GoogleReader(auth)

        if not reader.buildSubscriptionList():
            # XXX: better error recovery here?
            return False

        feeds = {}
        # First loop quickly creates Feed objects... for speedier UI?
        for f in reader.feeds:
            feed = Feed.create_and_subscribe(f.title, f.feedUrl, f.siteUrl, user)
            feeds[f.feedUrl] = feed
            userfeed = feed.userfeed(user)
            for c in f.categories:
                userfeed.tags.add(c.label)

        # Next, import all the items from the feeds
        for f in reader.feeds:
            feed = feeds[f.feedUrl]

            f.loadItems(loadLimit=loadLimit)
            for e in f.items:
                if e.url is None:
                    continue
                _new_user_item(user, feed, e)

        # Finally, import the special items
        reader.makeSpecialFeeds()
        special = reader.specialFeeds.keys()
        special.remove('read')
        special.remove('reading-list')
        for sf in special:
            f = reader.specialFeeds[sf]
            f.loadItems(loadLimit=loadLimit)
            for e in f.items:
                try:
                    feed = feeds[e.feed.feedUrl]
                except KeyError:
                    # Dammit, google. WTF are these beasties?
                    # u'user/00109242490472324272/source/com.google/link'
                    if e.feed.feedUrl.startswith('user/'):
                        link = Feed.autodiscover(e.feed.siteUrl)
                        if not link:
                            link = e.feed.feedUrl
                    feed = Feed.create_raw(e.feed.title, link, e.feed.siteUrl)
                    feeds[e.feed.feedUrl] = feed

                user_item = _new_user_item(user, feed, e)

                if sf == 'like':
                    user_item.tags.add('imported', 'liked')
                elif sf == 'post' or sf == 'created':
                    user_item.tags.add('imported', 'notes')
                elif sf == 'broadcast':
                    user_item.tags.add('imported', 'shared')
                elif sf == 'broadcast-friends':
                    user_item.tags.add('imported', 'shared-with-you')
                elif sf == 'starred':
                    user_item.tags.add('imported')

                user_item.save()

        return True
