"""User profiles and per-section access control.

The original site stored permissions as single characters in an ``auth_app``
table ('1' = 癌症研究, '2' = 感染管控, 'F' = 全部) and read them out of the
session, which meant a tampered session granted access.  Here the grants are
rows keyed to the user and are always re-read from the database.
"""

from django.conf import settings
from django.db import models


class Section(models.TextChoices):
    """A navigable area of the site that access can be granted to."""

    RESEARCH = 'research', '癌症研究'
    INFECTION = 'infection', '感染管控'


class Profile(models.Model):
    """Per-user display and review settings (原 ``auth_user`` 的自訂欄位)."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile',
        verbose_name='使用者',
    )
    display_name = models.CharField('姓名', max_length=64, blank=True)
    organization = models.CharField('單位', max_length=64, blank=True)
    de_identification = models.BooleanField(
        '去識別化顯示', default=True, help_text='開啟時病患姓名以遮罩顯示'
    )
    can_see_all_reviews = models.BooleanField(
        '可檢視所有人的標註', default=False
    )
    can_edit_stage_definition = models.BooleanField(
        '可編輯階段定義', default=False
    )

    class Meta:
        verbose_name = verbose_name_plural = '使用者設定'

    def __str__(self):
        return f'{self.user.username} 的設定'


class SectionPermission(models.Model):
    """Grants a user access to one section of the site (原 ``auth_app``)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='section_permissions',
        verbose_name='使用者',
    )
    section = models.CharField('功能區塊', max_length=16, choices=Section.choices)

    class Meta:
        verbose_name = verbose_name_plural = '功能區塊權限'
        ordering = ['user_id', 'section']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'section'], name='unique_section_permission'
            )
        ]

    def __str__(self):
        return f'{self.user.username} → {self.get_section_display()}'


class TopicPermission(models.Model):
    """Grants a user access to one research topic (原 ``auth_disease``)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='topic_permissions',
        verbose_name='使用者',
    )
    topic = models.ForeignKey(
        'research.ResearchTopic',
        on_delete=models.CASCADE,
        related_name='permissions',
        verbose_name='研究主題',
    )

    class Meta:
        verbose_name = verbose_name_plural = '研究主題權限'
        ordering = ['user_id', 'topic_id']
        constraints = [
            models.UniqueConstraint(fields=['user', 'topic'], name='unique_topic_permission')
        ]

    def __str__(self):
        return f'{self.user.username} → {self.topic.name}'
