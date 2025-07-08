import { useState } from 'react';
import { User, LogOut, Trash2, Mail, Calendar } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/components/ui/Button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/Dialog';
import { useGlobalContext } from '@/context/GlobalContext';
import { authApi } from '@/services/api';
import { formatDate } from '@/lib/utils';
import { toast } from 'sonner';
import { useNavigate } from 'react-router-dom';
import { LoadingScreen } from '@/components/LoadingScreen';

export function ProfilePage() {
  const { t } = useTranslation();
  const { state, dispatch } = useGlobalContext();
  const { user, isLoading } = state;
  const navigate = useNavigate();
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isLoggingOut, setIsLoggingOut] = useState(false);

  // Show loading screen while checking auth state
  if (isLoading) {
    return <LoadingScreen />;
  }

  // If not logged in, show login prompt
  if (!user) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="flex items-center justify-center min-h-[60vh]">
          <div className="text-center">
            <User className="h-16 w-16 text-muted-foreground mx-auto mb-4" />
            <h2 className="text-2xl font-bold mb-2">{t('profile.notLoggedIn.title')}</h2>
            <p className="text-muted-foreground mb-6">
              {t('profile.notLoggedIn.description')}
            </p>
            <Button onClick={() => navigate('/login')}>
              {t('profile.notLoggedIn.login')}
            </Button>
          </div>
        </div>
      </div>
    );
  }

  const handleLogout = async () => {
    try {
      setIsLoggingOut(true);
      await authApi.logout();

      localStorage.removeItem('access_token'); 

      dispatch({ type: 'CLEAR_STATE_PRESERVE_LIST' });
      toast.success(t('profile.success.loggedOut'), { duration: 2000 });
      navigate('/');
    } catch (error) {
      console.error('Logout failed:', error);
      localStorage.removeItem('access_token');
      dispatch({ type: 'CLEAR_STATE_PRESERVE_LIST' });
      toast.error(t('profile.errors.logoutError'), { duration: 2000 });
    } finally {
      setIsLoggingOut(false);
    }
  };

  const handleDeleteAccount = async () => {
    try {
      setIsDeleting(true);
      await authApi.deleteAccount();
      dispatch({ type: 'CLEAR_STATE' });
      localStorage.clear();
      toast.success(t('profile.success.accountDeleted'), { duration: 2000 });
      navigate('/');
    } catch (error) {
      console.error('Account deletion failed:', error);
      toast.error(t('profile.errors.deleteError'), { duration: 2000 });
    } finally {
      setIsDeleting(false);
      setShowDeleteDialog(false);
    }
  };

  return (
    <div className="container mx-auto px-4 py-8">
      <div className="max-w-2xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-bold mb-2">{t('profile.title')}</h1>
          <p className="text-muted-foreground">
            {t('profile.subtitle')}
          </p>
        </div>

        <div className="space-y-6">
          {/* User Info Card */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center space-x-2">
                <User className="h-5 w-5" />
                <span>{t('profile.userInfo.title')}</span>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center space-x-3">
                <Mail className="h-4 w-4 text-muted-foreground" />
                <div>
                  <p className="text-sm font-medium">{t('profile.userInfo.email')}</p>
                  <p className="text-sm text-muted-foreground">{user.email}</p>
                </div>
              </div>
              
              <div className="flex items-center space-x-3">
                <User className="h-4 w-4 text-muted-foreground" />
                <div>
                  <p className="text-sm font-medium">{t('profile.userInfo.name')}</p>
                  <p className="text-sm text-muted-foreground">{user.full_name}</p>
                </div>
              </div>
              
              <div className="flex items-center space-x-3">
                <Calendar className="h-4 w-4 text-muted-foreground" />
                <div>
                  <p className="text-sm font-medium">{t('profile.userInfo.registrationDate')}</p>
                  <p className="text-sm text-muted-foreground">
                    {formatDate(user.created_at)}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Statistics Card */}
          <Card>
            <CardHeader>
              <CardTitle>{t('profile.statistics.title')}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-4">
                <div className="text-center p-4 bg-muted/30 rounded-lg">
                  <div className="text-2xl font-bold text-primary">
                    {state.history.length}
                  </div>
                  <p className="text-sm text-muted-foreground">{t('profile.statistics.dialogs')}</p>
                </div>
                <div className="text-center p-4 bg-muted/30 rounded-lg">
                  <div className="text-2xl font-bold text-primary">
                    {state.considerationList.length}
                  </div>
                  <p className="text-sm text-muted-foreground">{t('profile.statistics.companies')}</p>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Actions Card */}
          <Card>
            <CardHeader>
              <CardTitle>{t('profile.actions.title')}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <Button
                variant="outline"
                onClick={handleLogout}
                disabled={isLoggingOut}
                className="w-full justify-start"
              >
                <LogOut className="h-4 w-4 mr-2" />
                {isLoggingOut ? t('profile.actions.loggingOut') : t('profile.actions.logout')}
              </Button>
              
              <Button
                variant="destructive"
                onClick={() => setShowDeleteDialog(true)}
                className="w-full justify-start"
              >
                <Trash2 className="h-4 w-4 mr-2" />
                {t('profile.actions.deleteAccount')}
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Delete Account Dialog */}
      <Dialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('profile.deleteDialog.title')}</DialogTitle>
            <DialogDescription>
              {t('profile.deleteDialog.description')}
            </DialogDescription>
          </DialogHeader>
          
          <div className="flex justify-end space-x-2 mt-6">
            <Button
              variant="outline"
              onClick={() => setShowDeleteDialog(false)}
              disabled={isDeleting}
            >
              {t('profile.deleteDialog.cancel')}
            </Button>
            <Button
              variant="destructive"
              onClick={handleDeleteAccount}
              disabled={isDeleting}
            >
              {isDeleting ? t('profile.actions.deleting') : t('profile.deleteDialog.confirm')}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}