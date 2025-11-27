"""
Activity Dashboard Views
========================

Comprehensive activity tracking dashboard for brokers and admins.
Provides real-time activity feed, analytics, and filtering capabilities.
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, F
from django.utils import timezone
from django.http import JsonResponse
from django.core.paginator import Paginator
from datetime import datetime, timedelta
from .models import Applicant, ApplicantActivity
from .activity_tracker import ActivityTracker
import json


@login_required
def activity_dashboard(request):
    """
    Main activity dashboard view for brokers and admins
    Shows comprehensive activity tracking and analytics
    """
    # Check permissions - only brokers and admins
    if not (request.user.is_superuser or request.user.is_broker or request.user.is_staff):
        return redirect('home')
    
    # Get filter parameters
    applicant_id = request.GET.get('applicant')
    activity_type = request.GET.get('type')
    date_range = request.GET.get('range', '7')  # Default to last 7 days
    search_query = request.GET.get('search')
    
    # Build base queryset
    activities = ApplicantActivity.objects.select_related(
        'applicant', 'triggered_by'
    ).order_by('-created_at')
    
    # Apply filters
    if applicant_id:
        activities = activities.filter(applicant_id=applicant_id)
    
    if activity_type:
        activities = activities.filter(activity_type=activity_type)
    
    if search_query:
        activities = activities.filter(
            Q(description__icontains=search_query) |
            Q(applicant__first_name__icontains=search_query) |
            Q(applicant__last_name__icontains=search_query) |
            Q(applicant__email__icontains=search_query)
        )
    
    # Date range filter
    if date_range != 'all':
        try:
            days = int(date_range)
            cutoff_date = timezone.now() - timedelta(days=days)
            activities = activities.filter(created_at__gte=cutoff_date)
        except ValueError:
            pass
    
    # Get statistics for the filtered period
    statistics = get_activity_statistics(activities)
    
    # Get activity type breakdown
    type_breakdown = activities.values('activity_type').annotate(
        count=Count('id')
    ).order_by('-count')[:10]
    
    # Get most active applicants
    active_applicants = activities.values(
        'applicant__id', 
        'applicant__first_name', 
        'applicant__last_name'
    ).annotate(
        activity_count=Count('id')
    ).order_by('-activity_count')[:10]
    
    # Paginate activities
    paginator = Paginator(activities, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get all applicants for filter dropdown
    all_applicants = Applicant.objects.all().order_by('last_name', 'first_name')
    
    # Get unique activity types for filter
    activity_types = ApplicantActivity.ACTIVITY_TYPES
    
    context = {
        'page_obj': page_obj,
        'statistics': statistics,
        'type_breakdown': type_breakdown,
        'active_applicants': active_applicants,
        'all_applicants': all_applicants,
        'activity_types': activity_types,
        'filters': {
            'applicant_id': applicant_id,
            'activity_type': activity_type,
            'date_range': date_range,
            'search_query': search_query,
        },
        'total_count': activities.count(),
    }
    
    return render(request, 'applicants/activity_dashboard.html', context)


@login_required
def activity_timeline(request, applicant_id):
    """
    Show detailed activity timeline for a specific applicant
    """
    applicant = get_object_or_404(Applicant, id=applicant_id)
    
    # Check permissions
    if not (request.user.is_superuser or request.user.is_broker or request.user.is_staff):
        return redirect('applicant_overview', applicant_id=applicant_id)
    
    # Get all activities for this applicant
    activities = ApplicantActivity.objects.filter(
        applicant=applicant
    ).select_related('triggered_by').order_by('-created_at')
    
    # Group activities by date
    activities_by_date = {}
    for activity in activities:
        date_key = activity.created_at.date()
        if date_key not in activities_by_date:
            activities_by_date[date_key] = []
        activities_by_date[date_key].append(activity)
    
    # Get summary statistics
    summary = ActivityTracker.get_activity_summary(applicant, days=30)
    
    context = {
        'applicant': applicant,
        'activities_by_date': activities_by_date,
        'summary': summary,
        'total_activities': activities.count(),
    }
    
    return render(request, 'applicants/activity_timeline.html', context)


@login_required
def activity_analytics_api(request):
    """
    API endpoint for activity analytics data (for charts)
    """
    if not (request.user.is_superuser or request.user.is_broker or request.user.is_staff):
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    # Get parameters
    days = int(request.GET.get('days', 7))
    applicant_id = request.GET.get('applicant')
    
    # Build queryset
    cutoff_date = timezone.now() - timedelta(days=days)
    activities = ApplicantActivity.objects.filter(created_at__gte=cutoff_date)
    
    if applicant_id:
        activities = activities.filter(applicant_id=applicant_id)
    
    # Activity trend by day
    daily_trend = []
    for i in range(days, -1, -1):
        date = timezone.now().date() - timedelta(days=i)
        count = activities.filter(
            created_at__date=date
        ).count()
        daily_trend.append({
            'date': date.isoformat(),
            'count': count
        })
    
    # Activity type distribution
    type_distribution = list(
        activities.values('activity_type').annotate(
            count=Count('id')
        ).order_by('-count')
    )
    
    # Peak hours analysis
    hourly_distribution = []
    for hour in range(24):
        count = activities.filter(
            created_at__hour=hour
        ).count()
        hourly_distribution.append({
            'hour': hour,
            'count': count
        })
    
    # Most viewed apartments
    apartment_views = activities.filter(
        activity_type='apartment_viewed'
    ).values('metadata').annotate(
        count=Count('id')
    ).order_by('-count')[:10]
    
    most_viewed_apartments = []
    for view in apartment_views:
        metadata = view['metadata'] or {}
        if 'apartment_id' in metadata:
            most_viewed_apartments.append({
                'apartment_id': metadata.get('apartment_id'),
                'building_name': metadata.get('building_name', 'Unknown'),
                'unit_number': metadata.get('unit_number', ''),
                'count': view['count']
            })
    
    # Heatmap data - activities by day of week and hour
    from django.db.models.functions import ExtractWeekDay, ExtractHour
    
    heatmap_data = []
    heatmap_qs = activities.annotate(
        day_of_week=ExtractWeekDay('created_at'),  # 1-7 (Sunday-Saturday)
        hour=ExtractHour('created_at')
    ).values('day_of_week', 'hour').annotate(
        count=Count('id')
    ).order_by('day_of_week', 'hour')
    
    for item in heatmap_qs:
        # Django's ExtractWeekDay returns 1-7 (Sunday=1, Saturday=7)
        # Convert to 0-6 for JavaScript (Sunday=0, Saturday=6)
        day = item['day_of_week'] - 1
        heatmap_data.append({
            'day_of_week': day,
            'hour': item['hour'],
            'count': item['count']
        })
    
    # Weekly pattern - activities by day of week
    weekly_pattern = activities.annotate(
        day_of_week=ExtractWeekDay('created_at')
    ).values('day_of_week').annotate(
        count=Count('id')
    ).order_by('day_of_week')
    
    weekly_data = []
    day_names = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
    for item in weekly_pattern:
        weekly_data.append({
            'day': day_names[item['day_of_week'] - 1],
            'count': item['count']
        })
    
    return JsonResponse({
        'daily_trend': daily_trend,
        'type_distribution': type_distribution,
        'hourly_distribution': hourly_distribution,
        'most_viewed_apartments': most_viewed_apartments,
        'heatmap_data': heatmap_data,
        'weekly_pattern': weekly_data,
    })


def get_activity_statistics(activities_queryset):
    """
    Calculate statistics for a given activities queryset
    """
    total = activities_queryset.count()
    
    if total == 0:
        return {
            'total': 0,
            'today': 0,
            'this_week': 0,
            'unique_applicants': 0,
            'most_common_type': 'N/A',
            'avg_per_day': 0,
        }
    
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)
    
    # Count activities
    today_count = activities_queryset.filter(created_at__date=today).count()
    week_count = activities_queryset.filter(created_at__date__gte=week_ago).count()
    
    # Unique applicants
    unique_applicants = activities_queryset.values('applicant').distinct().count()
    
    # Most common activity type
    most_common = activities_queryset.values('activity_type').annotate(
        count=Count('id')
    ).order_by('-count').first()
    
    most_common_type = most_common['activity_type'] if most_common else 'N/A'
    
    # Average per day (for the queried period)
    first_activity = activities_queryset.order_by('created_at').first()
    if first_activity:
        days_span = (timezone.now().date() - first_activity.created_at.date()).days + 1
        avg_per_day = round(total / days_span, 1)
    else:
        avg_per_day = 0
    
    return {
        'total': total,
        'today': today_count,
        'this_week': week_count,
        'unique_applicants': unique_applicants,
        'most_common_type': most_common_type,
        'avg_per_day': avg_per_day,
    }