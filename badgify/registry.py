# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import logging

logger = logging.getLogger('badgify')


class BadgifyRegistry(object):
    """
    Badge recipes registry.
    """

    def __init__(self):
        """
        Initializes a new registry.
        """
        self._registry = {}

    @property
    def recipes(self):
        """
        Returns all registered recipes (keys are recipe's badge slugs and values
        are recipe instances.
        """
        return self._registry

    @property
    def registered(self):
        """
        Returns registered recipes list (badge slugs).
        """
        return self._registry.keys()

    def register(self, recipe):
        """
        Registers a new recipe class.
        """
        if isinstance(recipe, (list, tuple)):
            for item in recipe:
                recipe = self.get_recipe_instance_from_class(item)
                self._registry[recipe.slug] = recipe
        else:
            recipe = self.get_recipe_instance_from_class(recipe)
            self._registry[recipe.slug] = recipe

    def unregister(self, recipe):
        """
        Unregisters a given recipe class.
        """
        recipe = self.get_recipe_instance_from_class(recipe)
        if recipe.slug in self._registry:
            del self._registry[recipe.slug]

    def clear(self):
        """
        Clears the registry (removes all registered classes).
        """
        self._registry = {}


    def get_recipe_instance(self, badge):
        """
        Returns the recipe instance for the given badge slug.
        If badge has not been registered, raises ``exceptions.BadgeNotFound``.
        """
        from .exceptions import BadgeNotFound
        if self._registry.has_key(badge):
            return self.recipes[badge]
        raise BadgeNotFound()

    def get_recipe_instances(self, badges=None, excluded=None):
        """
        Returns all recipe instances or just those for the given badges.
        """
        if badges:
            if not isinstance(badges, (list, tuple)):
                badges = [badges]

        if excluded:
            if not isinstance(excluded, (list, tuple)):
                excluded = [excluded]
            badges = list(set(self.registered) - set(excluded))

        if badges:
            valid, invalid = self.get_recipe_instances_for_badges(badges=badges)
            return valid

        return self.recipes.values()

    def get_recipe_instances_for_badges(self, badges):
        """
        Takes a list of badge slugs and returns a tuple: ``(valid, invalid)``.
        """
        from .exceptions import BadgeNotFound

        valid, invalid = [], []

        if not isinstance(badges, (list, tuple)):
            badges = [badges]

        for badge in badges:
            try:
                recipe = self.get_recipe_instance(badge)
                valid.append(recipe)
            except BadgeNotFound:
                logger.debug('✘ Badge "%s" has not been registered', badge)
                invalid.append(badge)

        return (valid, invalid)

    @staticmethod
    def get_recipe_instance_from_class(klass):
        """
        Returns recipe instance from the given class ``klass``.
        """
        from .recipe import BaseRecipe
        assert issubclass(klass, BaseRecipe)
        return klass()

    def sync_badges(self, **kwargs):
        """
        Iterates over registered recipes and creates missing badges.
        """
        from django.db import reset_queries

        created_badges, failed_badges = [], []
        instances = self.get_recipe_instances()

        for instance in instances:
            reset_queries()
            badge, created, failed = instance.create_badge()
            if created:
                created_badges.append(badge)
            if failed:
                failed_badges.append(instance.slug)
            self._log_queries(instance)

        return (created_badges, failed_badges)

    def sync_users_count(self, **kwargs):
        """
        Iterates over registered recipes and denormalizes ``Badge.users.count()``
        into ``Badge.users_count`` field.
        """
        from django.db import reset_queries

        badges = kwargs.get('badges')
        excluded = kwargs.get('exclude_badges')

        instances = self.get_recipe_instances(badges=badges, excluded=excluded)

        updated_badges, unchanged_badges = [], []

        for instance in instances:
            reset_queries()
            badge, updated = instance.update_badge_users_count()
            if updated:
                updated_badges.append(badge)
            else:
                unchanged_badges.append(badge)
            self._log_queries(instance)

        return (updated_badges, unchanged_badges)

    def sync_awards(self, **kwargs):
        """
        Iterates over registered recipes and possibly creates awards.
        """
        from django.db import reset_queries

        badges = kwargs.get('badges')
        excluded = kwargs.get('exclude_badges')

        instances = self.get_recipe_instances(badges=badges, excluded=excluded)

        for instance in instances:
            reset_queries()
            instance.create_awards()
            self._log_queries(instance)

    @staticmethod
    def _log_queries(instance):
        """
        Logs recipe instance SQL queries (actually, only time).
        """
        from django.db import connection

        logger.debug(
            '⚐ Badge %s: SQL queries time %.2f second(s)',
            instance.slug,
            sum([float(q['time']) for q in connection.queries]))


def _autodiscover(recipes):
    import copy
    from django.conf import settings
    from django.utils.importlib import import_module
    from django.utils.module_loading import module_has_submodule
    for app in settings.INSTALLED_APPS:
        mod = import_module(app)
        try:
            before_import_recipes = copy.copy(recipes)
            import_module('%s.badgify_recipes' % app)
        except:
            recipes = before_import_recipes
            if module_has_submodule(mod, 'badgify_recipes'):
                raise


registry = BadgifyRegistry()


def autodiscover():
    _autodiscover(registry)


def register(*args, **kwargs):
    return registry.register(*args, **kwargs)
