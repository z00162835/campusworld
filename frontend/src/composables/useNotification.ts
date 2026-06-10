/**
 * Notification composable - ElMessage wrapper
 */
import { ElMessage, ElMessageBox } from 'element-plus'
import i18n from '@/locales'

export function useNotification() {
  const success = (message: string) => ElMessage.success(message)
  const error = (message: string) => ElMessage.error(message)
  const warning = (message: string) => ElMessage.warning(message)
  const info = (message: string) => ElMessage.info(message)

  const confirm = (message: string, title = i18n.global.t('notification.confirmTitle')) => {
    return ElMessageBox.confirm(message, title, {
      confirmButtonText: i18n.global.t('notification.confirmButton'),
      cancelButtonText: i18n.global.t('notification.cancelButton'),
      type: 'warning',
    })
  }

  return {
    success,
    error,
    warning,
    info,
    confirm,
  }
}
