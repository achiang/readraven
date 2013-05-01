from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.shortcuts import render_to_response
from django.template import RequestContext

User = get_user_model()


def index(request):
    if request.user.is_authenticated() and request.user.is_customer():
        return HttpResponseRedirect(reverse('raven.views.home'))
    return render_to_response(
        'raven/index.html',
        context_instance=RequestContext(request))


@login_required
@user_passes_test(lambda u: u.is_customer(), login_url='/usher/sign_up')
def home(request):
    return render_to_response(
        'raven/home.html',
        context_instance=RequestContext(request))
