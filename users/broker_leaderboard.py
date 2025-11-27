"""
Broker Leaderboard Service
==========================

Tracks and ranks broker performance across key metrics:
- Applications Created
- Applications Approved  
- Conversion Rate (Approval %)
- Revenue Generated
- Recent Activity (30 days)
- Overall Performance Score

Scoring Algorithm:
- Applications Created: 10 points each
- Applications Approved: 25 points each  
- Conversion Rate Bonus: Up to 50 points (50% = 25pts, 100% = 50pts)
- Recent Activity Bonus: Up to 25 points (active in last 7 days)
"""

from django.contrib.auth import get_user_model
from django.db.models import Count, Q, F, Avg
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from typing import List, Dict
import logging

User = get_user_model()
logger = logging.getLogger(__name__)


class BrokerLeaderboardService:
    """
    Service for calculating broker performance metrics and rankings
    """
    
    # Scoring weights
    POINTS_PER_APPLICATION = 10
    POINTS_PER_APPROVAL = 25
    MAX_CONVERSION_BONUS = 50
    MAX_RECENT_ACTIVITY_BONUS = 25
    APPLICATION_FEE = Decimal('50.00')  # Default application fee
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}")
        
    def get_broker_leaderboard(self, limit: int = 20) -> List[Dict]:
        """
        Get ranked list of brokers with performance metrics
        Optimized to use database aggregation instead of N+1 queries.
        
        Args:
            limit: Maximum number of brokers to return
            
        Returns:
            List of broker performance dictionaries sorted by score
        """
        from applications.models import Application
        
        # Recent activity (last 30 days)
        thirty_days_ago = timezone.now() - timedelta(days=30)
        
        # Get all active brokers with pre-calculated metrics
        # Uses application_set (default reverse relation) for aggregation
        brokers = User.objects.filter(
            is_broker=True,
            is_active=True
        ).select_related('broker_profile').annotate(
            annotated_total_apps=Count('application_set'),
            annotated_approved_apps=Count('application_set', filter=Q(application_set__status='APPROVED')),
            annotated_rejected_apps=Count('application_set', filter=Q(application_set__status='REJECTED')),
            annotated_pending_apps=Count('application_set', filter=Q(application_set__status='PENDING')),
            annotated_recent_apps=Count('application_set', filter=Q(application_set__created_at__gte=thirty_days_ago)),
            annotated_last_activity=Max('application_set__created_at')
        )
        
        leaderboard = []
        
        for broker in brokers:
            metrics = self._calculate_broker_metrics(broker)
            leaderboard.append(metrics)
        
        # Sort by total score (highest first)
        leaderboard.sort(key=lambda x: x['total_score'], reverse=True)
        
        # Add ranking
        for rank, broker_data in enumerate(leaderboard, 1):
            broker_data['rank'] = rank
            broker_data['rank_change'] = self._calculate_rank_change(broker_data['broker'], rank)
        
        return leaderboard[:limit]
    
    def _calculate_broker_metrics(self, broker) -> Dict:
        """Calculate comprehensive metrics for a single broker using annotated data"""
        
        # Use annotated data if available, otherwise fall back to queries (for backward compatibility/testing)
        if hasattr(broker, 'annotated_total_apps'):
            total_applications = broker.annotated_total_apps
            approved_applications = broker.annotated_approved_apps
            rejected_applications = broker.annotated_rejected_apps
            pending_applications = broker.annotated_pending_apps
            recent_applications = broker.annotated_recent_apps
            last_activity_date = broker.annotated_last_activity
        else:
            # Fallback for non-annotated querysets
            from applications.models import Application
            all_apps = Application.objects.filter(broker=broker)
            total_applications = all_apps.count()
            approved_applications = all_apps.filter(status='APPROVED').count()
            rejected_applications = all_apps.filter(status='REJECTED').count()
            pending_applications = all_apps.filter(status='PENDING').count()
            
            thirty_days_ago = timezone.now() - timedelta(days=30)
            recent_applications = all_apps.filter(created_at__gte=thirty_days_ago).count()
            last_activity = all_apps.order_by('-created_at').first()
            last_activity_date = last_activity.created_at if last_activity else None
        
        # Calculate conversion rate
        conversion_rate = (approved_applications / total_applications * 100) if total_applications > 0 else 0
        
        # Calculate revenue (applications * fee)
        revenue_generated = total_applications * self.APPLICATION_FEE
        
        # Calculate scores
        application_score = total_applications * self.POINTS_PER_APPLICATION
        approval_score = approved_applications * self.POINTS_PER_APPROVAL
        conversion_bonus = self._calculate_conversion_bonus(conversion_rate)
        activity_bonus = self._calculate_activity_bonus(recent_applications, total_applications)
        
        total_score = application_score + approval_score + conversion_bonus + activity_bonus
        
        # Get broker profile info
        broker_name = self._get_broker_display_name(broker)
        
        # Recent activity status
        days_since_activity = None
        activity_status = "Never Active"
        
        if last_activity_date:
            days_since_activity = (timezone.now() - last_activity_date).days
            if days_since_activity == 0:
                activity_status = "Active Today"
            elif days_since_activity == 1:
                activity_status = "Active Yesterday"
            elif days_since_activity <= 7:
                activity_status = f"Active {days_since_activity} days ago"
            elif days_since_activity <= 30:
                activity_status = f"Active {days_since_activity} days ago"
            else:
                activity_status = "Inactive (30+ days)"
        
        # Performance level
        performance_level = self._get_performance_level(total_score, total_applications)
        
        return {
            'broker': broker,
            'broker_name': broker_name,
            'broker_email': broker.email,
            
            # Core metrics
            'total_applications': total_applications,
            'approved_applications': approved_applications,
            'rejected_applications': rejected_applications,
            'pending_applications': pending_applications,
            'conversion_rate': round(conversion_rate, 1),
            'revenue_generated': revenue_generated,
            
            # Recent activity
            'recent_applications': recent_applications,
            'days_since_activity': days_since_activity,
            'activity_status': activity_status,
            
            # Scoring
            'application_score': application_score,
            'approval_score': approval_score,
            'conversion_bonus': conversion_bonus,
            'activity_bonus': activity_bonus,
            'total_score': total_score,
            
            # Display info
            'performance_level': performance_level,
            'last_activity_date': last_activity_date,
        }
    
    def _calculate_conversion_bonus(self, conversion_rate: float) -> int:
        """Calculate bonus points for conversion rate"""
        if conversion_rate >= 90:
            return self.MAX_CONVERSION_BONUS
        elif conversion_rate >= 75:
            return int(self.MAX_CONVERSION_BONUS * 0.8)  # 40 points
        elif conversion_rate >= 50:
            return int(self.MAX_CONVERSION_BONUS * 0.5)  # 25 points
        elif conversion_rate >= 25:
            return int(self.MAX_CONVERSION_BONUS * 0.3)  # 15 points
        else:
            return 0
    
    def _calculate_activity_bonus(self, recent_applications: int, total_applications: int) -> int:
        """Calculate bonus points for recent activity"""
        if total_applications == 0:
            return 0
        
        # Percentage of applications in last 30 days
        activity_percentage = (recent_applications / total_applications) if total_applications > 0 else 0
        
        if activity_percentage >= 0.3:  # 30% of activity in last 30 days
            return self.MAX_RECENT_ACTIVITY_BONUS
        elif activity_percentage >= 0.2:  # 20%
            return int(self.MAX_RECENT_ACTIVITY_BONUS * 0.7)  # 17 points
        elif activity_percentage >= 0.1:  # 10%
            return int(self.MAX_RECENT_ACTIVITY_BONUS * 0.4)  # 10 points
        else:
            return 0
    
    def _get_broker_display_name(self, broker) -> str:
        """Get display name for broker"""
        try:
            if hasattr(broker, 'broker_profile') and broker.broker_profile:
                profile = broker.broker_profile
                return f"{profile.first_name} {profile.last_name}"
        except:
            pass
        
        # Fallback to email
        return broker.email.split('@')[0].title()
    
    def _get_performance_level(self, total_score: int, total_applications: int) -> Dict:
        """Determine performance level and badge"""
        if total_score >= 500:
            return {
                'level': 'Elite Broker',
                'badge': 'elite',
                'color': 'gold',
                'icon': 'fa-crown'
            }
        elif total_score >= 300:
            return {
                'level': 'Senior Broker',
                'badge': 'senior', 
                'color': 'primary',
                'icon': 'fa-star'
            }
        elif total_score >= 150:
            return {
                'level': 'Active Broker',
                'badge': 'active',
                'color': 'success',
                'icon': 'fa-check-circle'
            }
        elif total_applications > 0:
            return {
                'level': 'New Broker',
                'badge': 'new',
                'color': 'info',
                'icon': 'fa-seedling'
            }
        else:
            return {
                'level': 'Getting Started',
                'badge': 'starter',
                'color': 'muted',
                'icon': 'fa-play'
            }
    
    def _calculate_rank_change(self, broker, current_rank: int) -> str:
        """Calculate rank change from previous period (placeholder for future implementation)"""
        # TODO: Implement historical ranking comparison
        # For now, return neutral
        return "new"
    
    def get_broker_summary_stats(self) -> Dict:
        """Get overall broker performance summary"""
        from applications.models import Application
        
        brokers = User.objects.filter(is_broker=True, is_active=True)
        total_brokers = brokers.count()
        
        if total_brokers == 0:
            return {
                'total_brokers': 0,
                'active_brokers': 0,
                'total_applications': 0,
                'total_revenue': 0,
                'average_conversion_rate': 0,
            }
        
        # Calculate aggregate stats
        all_applications = Application.objects.filter(broker__in=brokers)
        total_applications = all_applications.count()
        total_approved = all_applications.filter(status='APPROVED').count()
        
        # Active brokers (created application in last 30 days)
        thirty_days_ago = timezone.now() - timedelta(days=30)
        active_brokers = brokers.filter(
            application_set__created_at__gte=thirty_days_ago
        ).distinct().count()
        
        # Calculate stats
        total_revenue = total_applications * self.APPLICATION_FEE
        avg_conversion_rate = (total_approved / total_applications * 100) if total_applications > 0 else 0
        
        return {
            'total_brokers': total_brokers,
            'active_brokers': active_brokers,
            'total_applications': total_applications,
            'total_revenue': total_revenue,
            'average_conversion_rate': round(avg_conversion_rate, 1),
            'top_performers': total_brokers // 4 if total_brokers > 4 else 1,  # Top 25%
        }


# Utility function for easy access
def get_broker_leaderboard(limit: int = 20) -> List[Dict]:
    """
    Convenience function to get broker leaderboard
    
    Args:
        limit: Maximum number of brokers to return
        
    Returns:
        List of broker performance dictionaries
    """
    service = BrokerLeaderboardService()
    return service.get_broker_leaderboard(limit)