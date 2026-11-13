"""
# // ==============================================================================
# // KCC CLASSSTAMP - ANALYTICS SERVICE
# // ==============================================================================
# // Subsystem: Predictive Analytics & At-Risk Detection
# // Description: Provides attendance prediction and at-risk student identification
# //              using linear regression models.
# // Requirements: Requirement 15 - Predictive Attendance Analytics
# // ==============================================================================
"""

import logging
from collections import defaultdict
from typing import Optional, List, Tuple

from django.utils import timezone

logger = logging.getLogger(__name__)

# // Predictive analytics needs numpy + scikit-learn (declared in
# // requirements.txt). The rest of the app — dashboards, attendance, reports —
# // must still boot when those wheels are absent, so the import is optional and
# // predictions simply report "no data" instead of taking the whole site down.
try:
    import numpy as np
    from sklearn.linear_model import LinearRegression

    ML_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only on slim installs
    np = None
    LinearRegression = None
    ML_AVAILABLE = False
    logger.warning(
        'numpy/scikit-learn are not installed: predictive attendance analytics '
        'is disabled. Install with: pip install -r requirements.txt'
    )

# Task 5.3: explicit algorithm version. Bump this when the prediction
# model or configuration changes. One AuditEvent is written the first time
# a version is used, not once per student per page view.
PREDICTION_ALGORITHM_VERSION = 'linreg-cumulative-v1'


class AnalyticsService:
    """
    Attendance analytics and prediction service.
    Provides predictive analytics for student attendance patterns.
    """
    
    @staticmethod
    def predict_final_attendance(enrollment) -> Optional[float]:
        """
        Predict final attendance rate for an enrollment using linear regression.
        
        Args:
            enrollment: Enrollment model instance
        
        Returns:
            Predicted final attendance percentage (0-100), or None if insufficient data.
        
        Requirements:
            - Minimum 5 sessions required for prediction
            - Uses time-series linear regression on cumulative attendance rate
        """
        if not ML_AVAILABLE:
            return None

        from apps.core.models import AttendanceRecord, ClassSession
        
        # Get all closed sessions for the class
        sessions = ClassSession.objects.filter(
            slot__class_obj=enrollment.class_obj,
            status=ClassSession.STATUS_CLOSED,
            session_date__lte=timezone.now().date()
        ).order_by('session_date')
        
        session_count = sessions.count()
        if session_count < 5:
            logger.debug(
                f'Insufficient data for prediction: enrollment {enrollment.pk} '
                f'has only {session_count} sessions (minimum 5 required)'
            )
            return None  # Insufficient data
        
        # Get attendance records for the student
        attendance_records = AttendanceRecord.objects.filter(
            session__in=sessions,
            student_profile=enrollment.student_profile
        ).select_related('session').order_by('session__session_date')
        
        # Build time series data
        X = []  # Session numbers
        y = []  # Cumulative attendance rates
        
        present_count = 0
        for i, session in enumerate(sessions, 1):
            # Check if student was present, late, or excused (all count as attended)
            record = attendance_records.filter(session=session).first()
            if record and record.status in (
                AttendanceRecord.STATUS_PRESENT,
                AttendanceRecord.STATUS_LATE,
                AttendanceRecord.STATUS_EXCUSED
            ):
                present_count += 1
            
            # Calculate cumulative attendance rate
            attendance_rate = (present_count / i) * 100.0
            X.append([i])
            y.append(attendance_rate)
        
        # Fit linear regression model
        try:
            X_array = np.array(X)
            y_array = np.array(y)
            
            model = LinearRegression()
            model.fit(X_array, y_array)
            
            # Predict for final session (estimate total sessions from academic year)
            estimated_total_sessions = AnalyticsService._estimate_total_sessions(enrollment)
            predicted_rate = model.predict([[estimated_total_sessions]])[0]
            
            # Clamp to 0-100 range
            final_prediction = max(0.0, min(100.0, predicted_rate))
            
            logger.debug(
                f'Prediction for enrollment {enrollment.pk}: '
                f'current sessions={session_count}, estimated total={estimated_total_sessions}, '
                f'predicted rate={final_prediction:.2f}%'
            )
            
            return final_prediction
            
        except Exception as e:
            logger.error(f'Error predicting attendance for enrollment {enrollment.pk}: {e}')
            return None
    
    @staticmethod
    def predict_class_attendance(class_obj):
        """
        // Task 5.2: advisory predictions for every actively enrolled student
        // in class_obj, using current-academic-year closed sessions.
        //
        // Loads sessions and records once (no per-student N+1). Returns a list
        // of dicts: {student_profile_id, prediction, insufficient_data}.
        // The result is advisory only — never an official pass/fail decision.
        """
        from apps.core.models import AttendanceRecord, ClassSession, Enrollment

        enrollments = Enrollment.objects.filter(
            class_obj=class_obj,
            status=Enrollment.STATUS_ACTIVE,
        ).values_list('student_profile_id', flat=True)
        student_ids = list(enrollments)
        if not student_ids:
            return []

        sessions = list(
            ClassSession.objects.filter(
                slot__class_obj=class_obj,
                status=ClassSession.STATUS_CLOSED,
                session_date__lte=timezone.now().date(),
            ).order_by('session_date').values('id', 'session_date')
        )
        if len(sessions) < 5:
            return [
                {
                    'student_profile_id': sid,
                    'prediction': None,
                    'insufficient_data': True,
                }
                for sid in student_ids
            ]

        records = AttendanceRecord.objects.filter(
            session_id__in=[s['id'] for s in sessions],
            student_profile_id__in=student_ids,
        ).values_list('student_profile_id', 'session_id', 'status')

        # student_id -> session_id -> 1 if attended (present/late/excused)
        attended = defaultdict(dict)
        for student_id, session_id, status in records:
            attended[student_id][session_id] = status in (
                AttendanceRecord.STATUS_PRESENT,
                AttendanceRecord.STATUS_LATE,
                AttendanceRecord.STATUS_EXCUSED,
            )

        session_ids = [s['id'] for s in sessions]
        estimated_total = AnalyticsService._estimate_total_sessions(
            type('EnrollmentStub', (), {'class_obj': class_obj})(),
        )

        results = []
        for sid in student_ids:
            per_session = attended.get(sid, {})
            present_count = 0
            X, y = [], []
            for i, session_id in enumerate(session_ids, 1):
                if per_session.get(session_id):
                    present_count += 1
                X.append([i])
                y.append((present_count / i) * 100.0)

            prediction = None
            try:
                model = LinearRegression()
                model.fit(np.array(X), np.array(y))
                predicted = model.predict([[estimated_total]])[0]
                prediction = max(0.0, min(100.0, float(predicted)))
            except Exception as exc:
                logger.warning('Batch prediction failed for student %s: %s', sid, exc)

            results.append({
                'student_profile_id': sid,
                'prediction': prediction,
                'insufficient_data': False,
            })
        return results

    @staticmethod
    def ensure_algorithm_version_audited():
        """
        // Task 5.3: record the algorithm version once per version, not once
        // per student per page view.
        """
        from apps.core.models import AuditEvent

        exists = AuditEvent.objects.filter(
            action='PREDICTION_ALGORITHM_VERSION',
            new_value=PREDICTION_ALGORITHM_VERSION,
        ).exists()
        if exists:
            return
        AuditEvent.objects.create(
            actor=None,
            action='PREDICTION_ALGORITHM_VERSION',
            object_type='AnalyticsService',
            object_id=PREDICTION_ALGORITHM_VERSION,
            new_value=PREDICTION_ALGORITHM_VERSION,
            reason=(
                'Advisory linear-regression attendance prediction '
                '(cumulative rate vs session index; 85% term-length estimate; '
                'minimum 5 sessions).'
            ),
        )

    @staticmethod
    def _estimate_total_sessions(enrollment) -> int:
        """
        Estimate total sessions for academic year based on weekly slots.
        
        Args:
            enrollment: Enrollment model instance
            
        Returns:
            Estimated total number of sessions for the academic year
        """
        # Get academic year date range
        academic_year = enrollment.class_obj.academic_year
        total_weeks = (academic_year.ends_on - academic_year.starts_on).days / 7.0
        
        # Get number of weekly slots
        slots_per_week = enrollment.class_obj.slots.filter(is_active=True).count()
        
        # Estimate total sessions (subtract holidays and exam weeks - assume 85% attendance rate)
        estimated_sessions = int(total_weeks * slots_per_week * 0.85)
        
        # Ensure minimum of 20 sessions
        return max(estimated_sessions, 20)
    
    @staticmethod
    def calculate_absence_rate(enrollment) -> float:
        """
        Calculate unexcused absence rate for an enrollment.
        
        Args:
            enrollment: Enrollment model instance
        
        Returns:
            Absence percentage (0-100)
        """
        from apps.core.models import AttendanceRecord, ClassSession
        
        # Get all closed sessions for the class
        sessions = ClassSession.objects.filter(
            slot__class_obj=enrollment.class_obj,
            status=ClassSession.STATUS_CLOSED
        )
        
        total_sessions = sessions.count()
        if total_sessions == 0:
            return 0.0
        
        # Count unexcused absences (only ABSENT status, not EXCUSED)
        absent_count = AttendanceRecord.objects.filter(
            session__in=sessions,
            student_profile=enrollment.student_profile,
            status=AttendanceRecord.STATUS_ABSENT
        ).count()
        
        absence_rate = (absent_count / total_sessions) * 100.0
        
        logger.debug(
            f'Absence rate for enrollment {enrollment.pk}: '
            f'{absent_count}/{total_sessions} = {absence_rate:.2f}%'
        )
        
        return absence_rate
    
    @staticmethod
    def calculate_at_risk_students(threshold: float = 20.0) -> List[Tuple]:
        """
        Identify students whose absence rate exceeds the threshold.
        
        Args:
            threshold: Absence percentage threshold (default 20%)
        
        Returns:
            List of (enrollment, absence_rate) tuples for at-risk students
        """
        from apps.core.models import Enrollment, AcademicYear
        
        # Get active academic year
        active_year = AcademicYear.objects.filter(is_active=True).first()
        if not active_year:
            logger.warning('No active academic year found for at-risk calculation')
            return []
        
        # Get all active enrollments in the current academic year
        enrollments = Enrollment.objects.filter(
            status=Enrollment.STATUS_ACTIVE,
            class_obj__academic_year=active_year
        ).select_related('student_profile', 'class_obj', 'class_obj__teacher_profile')
        
        at_risk = []
        for enrollment in enrollments:
            absence_rate = AnalyticsService.calculate_absence_rate(enrollment)
            if absence_rate >= threshold:
                at_risk.append((enrollment, absence_rate))
                logger.info(
                    f'At-risk student detected: {enrollment.student_profile} '
                    f'in {enrollment.class_obj.class_code} with {absence_rate:.2f}% absence rate'
                )
        
        logger.info(
            f'Found {len(at_risk)} at-risk students with absence rate >= {threshold}%'
        )
        
        return at_risk
