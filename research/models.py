"""Research-cohort curation.

Replaces ``researchTopic`` / ``diseaseGroup`` / ``correlationPatientDisease`` /
``allEvents`` / ``examStudy`` / ``ExamStudySeries_6`` / ``Localization``.

The original stored one row per image slice and checked the filesystem for
``.h5`` files.  The demo keeps the study/series records — which is what the
list pages actually display — and drops the pixel data entirely.
"""

from django.conf import settings
from django.db import models

from clinical.models import ClinicalEvent, Patient


class ResearchTopic(models.Model):
    """A research topic a cohort is collected for (原 ``researchTopic``)."""

    name = models.CharField('主題名稱', max_length=128, unique=True)
    description = models.TextField('說明', blank=True)

    class Meta:
        verbose_name = verbose_name_plural = '研究主題'
        ordering = ['id']

    def __str__(self):
        return self.name


class DiseaseGroup(models.Model):
    """Disease grouping used by the warehousing list (原 ``diseaseGroup``)."""

    name = models.CharField('疾病名稱', max_length=128, unique=True)

    class Meta:
        verbose_name = verbose_name_plural = '疾病分組'
        ordering = ['id']

    def __str__(self):
        return self.name


class PatientDisease(models.Model):
    """Which disease group a patient belongs to (原 ``correlationPatientDisease``)."""

    patient = models.ForeignKey(
        Patient, on_delete=models.CASCADE, related_name='diseases', verbose_name='病患'
    )
    disease = models.ForeignKey(
        DiseaseGroup, on_delete=models.CASCADE, related_name='patients', verbose_name='疾病分組'
    )

    class Meta:
        verbose_name = verbose_name_plural = '病患疾病關聯'
        constraints = [
            models.UniqueConstraint(
                fields=['patient', 'disease'], name='unique_patient_disease'
            )
        ]

    def __str__(self):
        return f'{self.patient.chart_no} / {self.disease.name}'


class ExamStudy(models.Model):
    """One imaging study record (metadata only — no pixel data in the demo)."""

    event = models.ForeignKey(
        ClinicalEvent, on_delete=models.CASCADE, related_name='studies', verbose_name='臨床事件'
    )
    study_id = models.CharField('檢查編號', max_length=32, db_index=True)
    series_id = models.CharField('序列編號', max_length=32)
    description = models.CharField('檢查說明', max_length=255, blank=True)
    series_description = models.CharField('序列說明', max_length=255, blank=True)
    slice_count = models.PositiveIntegerField('影像張數', default=0)
    hospital = models.CharField('院區', max_length=32, blank=True)

    class Meta:
        verbose_name = verbose_name_plural = '檢查紀錄'
        ordering = ['study_id', 'series_id']

    def __str__(self):
        return f'{self.study_id}/{self.series_id}'


class StageDefinition(models.Model):
    """A disease-stage label that a patient record can be confirmed against.

    Replaces the original ``EventDefinition`` table.
    """

    topic = models.ForeignKey(
        ResearchTopic,
        on_delete=models.CASCADE,
        related_name='stage_definitions',
        verbose_name='研究主題',
    )
    name = models.CharField('階段名稱', max_length=128)
    order = models.PositiveIntegerField('排序', default=0)

    class Meta:
        verbose_name = verbose_name_plural = '病患階段定義'
        ordering = ['topic_id', 'order']
        constraints = [
            models.UniqueConstraint(fields=['topic', 'name'], name='unique_stage_per_topic')
        ]

    def __str__(self):
        return f'{self.topic.name} / {self.name}'


class StageConfirmation(models.Model):
    """A reviewer's confirmation that a patient is at a given stage.

    Replaces the original ``Localization`` / ``annotation`` bookkeeping, which
    tracked "has this user labelled this patient yet".
    """

    patient = models.ForeignKey(
        Patient,
        on_delete=models.CASCADE,
        related_name='stage_confirmations',
        verbose_name='病患',
    )
    stage = models.ForeignKey(
        StageDefinition,
        on_delete=models.CASCADE,
        related_name='confirmations',
        verbose_name='階段',
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='stage_confirmations',
        verbose_name='確認者',
    )
    note = models.TextField('備註', blank=True)
    confirmed_at = models.DateTimeField('確認時間', auto_now_add=True)

    class Meta:
        verbose_name = verbose_name_plural = '階段確認紀錄'
        ordering = ['-confirmed_at']
        constraints = [
            models.UniqueConstraint(
                fields=['patient', 'stage', 'reviewer'], name='unique_stage_confirmation'
            )
        ]

    def __str__(self):
        return f'{self.patient.chart_no} / {self.stage.name} / {self.reviewer}'
