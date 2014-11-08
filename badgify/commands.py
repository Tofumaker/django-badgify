# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import logging

from django.db import IntegrityError
from django.db.models import signals

from . import registry
from . import settings
from .models import Badge, Award
from .utils import get_user_ids_for_badge, get_award_objects_for_badge

logger = logging.getLogger(__name__)


def sync_badges(**kwargs):
    """
    Synchronizes badges from recipes.
    """
    badges = Badge.objects.all()
    new_badges = []

    for slug in registry.recipes:
        recipe = registry.recipes[slug]
        try:
            badges.get(slug=slug)
        except Badge.DoesNotExist:
            try:
                badge = badges.create(
                    name=recipe.name,
                    slug=slug,
                    description=recipe.description,
                    image=recipe.image)
                new_badges.append(badge)
            except IntegrityError:
                logger.debug('✘ Badge %s: IntegrityError', slug)

    if len(new_badges):
        for badge in new_badges:
            logger.debug('✓ Badge %s: created', badge.slug)


def sync_awards(**kwargs):
    """
    Loads registered recipes and synchronizes awards.
    """
    batch_size = kwargs.get('batch_size', None)

    if batch_size is None:
        batch_size = settings.AWARD_BULK_CREATE_BATCH_SIZE

    for slug in registry.recipes:

        recipe = registry.recipes[slug]
        badge = recipe.badge
        user_querysets = recipe.user_queryset

        logger.debug('→ Badge %s: syncing awards...', badge.slug)

        user_ids, user_ids_count = get_user_ids_for_badge(
            badge=badge,
            user_querysets=user_querysets)

        if not user_ids_count:
            logger.debug('✓ Badge %s: no new awards', badge.slug)
            continue

        logger.debug('→ Badge %s: found %d awards to save',
            badge.slug,
            user_ids_count)

        objects = get_award_objects_for_badge(
            badge=badge,
            user_ids=user_ids,
            batch_size=batch_size)

        try:
            Award.objects.bulk_create(objects, batch_size=batch_size)
            logger.debug('✓ Badge %s: created %d awards', badge.slug, user_ids_count)
            for obj in objects:
                signals.post_save.send(
                    sender=obj.__class__,
                    instance=obj,
                    created=True,
                    raw=True)
        except IntegrityError:
            logger.error('✘ Badge %s: IntegrityError for %d awards', badge.slug, user_ids_count)


def sync_counts(**kwargs):
    """
    Synchronizes badge counts.
    """
    for slug in registry.recipes:

        recipe = registry.recipes[slug]
        badge = recipe.badge
        logger.debug('→ Badge %s: syncing counts...', badge.slug)

        old_value = badge.users_count
        new_value = badge.users.count()

        if old_value != new_value:
            badge.users_count = new_value
            badge.save()
            logger.debug('✓ Badge %s: updated users count (from %d to %d)',
                badge.slug,
                old_value,
                new_value)
            continue

        logger.debug('✓ Badge %s: users count up-to-date (%d)',
            badge.slug,
            new_value)
