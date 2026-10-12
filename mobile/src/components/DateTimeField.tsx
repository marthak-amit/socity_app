import React from 'react';
import { Platform, Pressable, View } from 'react-native';
import DateTimePicker, { DateTimePickerAndroid } from '@react-native-community/datetimepicker';
import { useTranslation } from 'react-i18next';
import { Ionicons, T } from '@/components/ui';
import { colors, radius, space } from '@/theme';
import { formatDateTime } from '@/utils/dates';

/** Date + time field. Android: two native dialogs (date then time). iOS: compact native picker. */
export function DateTimeField({ label, value, onChange, onClear, placeholder }: {
  label: string; value: Date | null; onChange: (d: Date) => void; onClear?: () => void; placeholder?: string;
}) {
  const { i18n } = useTranslation();
  const open = () => {
    const base = value ?? new Date();
    DateTimePickerAndroid.open({
      value: base, mode: 'date', onChange: (e, date) => {
        if (e.type !== 'set' || !date) return;
        DateTimePickerAndroid.open({
          value: date, mode: 'time', is24Hour: false, onChange: (e2, time) => {
            if (e2.type === 'set' && time) { const d = new Date(date); d.setHours(time.getHours(), time.getMinutes(), 0, 0); onChange(d); }
          },
        });
      },
    });
  };
  return (
    <View style={{ gap: 4 }}>
      <T variant="label" color={colors.muted}>{label}</T>
      {Platform.OS === 'ios' ? (
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.sm }}>
          <DateTimePicker value={value ?? new Date()} mode="datetime" display="compact" onChange={(_, d) => d && onChange(d)} />
          {onClear && value ? <Pressable onPress={onClear}><Ionicons name="close-circle" size={20} color={colors.faint} /></Pressable> : null}
        </View>
      ) : (
        <Pressable onPress={open} style={{ flexDirection: 'row', alignItems: 'center', gap: space.sm, borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, backgroundColor: '#fff', minHeight: 48, paddingHorizontal: space.md }}>
          <Ionicons name="calendar-outline" size={20} color={colors.primary} />
          <T style={{ flex: 1 }} color={value ? colors.text : colors.faint}>{value ? formatDateTime(value.toISOString(), i18n.language) : placeholder}</T>
          {onClear && value ? <Pressable onPress={onClear} hitSlop={8}><Ionicons name="close-circle" size={20} color={colors.faint} /></Pressable> : null}
        </Pressable>
      )}
    </View>
  );
}
