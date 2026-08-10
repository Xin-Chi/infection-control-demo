"""Infection-control term curation.

Replaces the original ``Ontology`` / ``Infection_Category`` /
``InfectionCategoryPool`` / ``Infection_Conversion_*`` tables.  The workflow is:

1.  Terms (:class:`Token`) arrive in a pool, each proposed under a category.
2.  A reviewer confirms or abandons each pooled term
    (:class:`CategoryPoolEntry.status`).
3.  Confirmed terms are mapped onto a curated category
    (:class:`ConversionCategory` / :class:`ConversionEntry`).
"""

from django.db import models


class Token(models.Model):
    """A term extracted from report text (original ``Ontology``)."""

    text = models.CharField('字詞', max_length=255, unique=True)

    class Meta:
        verbose_name = verbose_name_plural = '字詞'
        ordering = ['text']

    def __str__(self):
        return self.text


class InfectionCategory(models.Model):
    """Proposed category a pooled term may belong to."""

    name = models.CharField('分類名稱', max_length=128, unique=True)

    class Meta:
        verbose_name = verbose_name_plural = '感染分類'
        ordering = ['id']

    def __str__(self):
        return self.name


class CategoryPoolEntry(models.Model):
    """A term awaiting review under a proposed category.

    The original schema used ``checked`` as an untyped integer
    (-1 abandoned / 0 pending / 1 confirmed); the states are named here.
    """

    class Status(models.IntegerChoices):
        ABANDONED = -1, '已捨棄'
        PENDING = 0, '待確認'
        CONFIRMED = 1, '已確認'

    category = models.ForeignKey(
        InfectionCategory,
        on_delete=models.CASCADE,
        related_name='pool_entries',
        verbose_name='感染分類',
    )
    token = models.ForeignKey(
        Token, on_delete=models.CASCADE, related_name='pool_entries', verbose_name='字詞'
    )
    status = models.IntegerField('狀態', choices=Status.choices, default=Status.PENDING)
    categorized_count = models.PositiveIntegerField('已歸類次數', default=0)

    class Meta:
        verbose_name = verbose_name_plural = '待歸類字詞'
        ordering = ['category_id', 'token_id']
        constraints = [
            models.UniqueConstraint(
                fields=['category', 'token'], name='unique_pool_entry_per_category'
            )
        ]

    def __str__(self):
        return f'{self.category.name} / {self.token.text}'


class ConversionCategory(models.Model):
    """A curated category that confirmed terms are mapped into."""

    name = models.CharField('分類名稱', max_length=128)
    pool = models.CharField('所屬詞庫', max_length=64)

    class Meta:
        verbose_name = verbose_name_plural = '歸類分類'
        ordering = ['id']
        constraints = [
            models.UniqueConstraint(
                fields=['name', 'pool'], name='unique_conversion_category_per_pool'
            )
        ]

    def __str__(self):
        return f'{self.pool} / {self.name}'


class ConversionEntry(models.Model):
    """Membership of a term in a curated category."""

    category = models.ForeignKey(
        ConversionCategory,
        on_delete=models.CASCADE,
        related_name='entries',
        verbose_name='歸類分類',
    )
    token = models.ForeignKey(
        Token,
        on_delete=models.CASCADE,
        related_name='conversion_entries',
        verbose_name='字詞',
    )

    class Meta:
        verbose_name = verbose_name_plural = '已歸類字詞'
        ordering = ['category_id', 'token_id']
        constraints = [
            models.UniqueConstraint(
                fields=['category', 'token'], name='unique_conversion_entry'
            )
        ]

    def __str__(self):
        return f'{self.category.name} / {self.token.text}'
