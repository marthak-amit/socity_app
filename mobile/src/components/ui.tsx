import React, { useEffect, useRef } from 'react';
import {
  ActivityIndicator, Alert, Animated, Pressable, RefreshControl, ScrollView, StyleProp, StyleSheet, Text, TextInput,
  TextInputProps, TextStyle, View, ViewStyle,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useTranslation } from 'react-i18next';
import type { TFunction } from 'i18next';
import { create } from 'zustand';
import { FONT_FAMILIES, Lang, colors, radius, shadow, space } from '@/theme';
import { ApiError } from '@/api/client';

type IconName = React.ComponentProps<typeof Ionicons>['name'];
export { Ionicons };

// ------------------------------------------------------------------ text
type Variant = 'display' | 'title' | 'heading' | 'body' | 'label' | 'caption';
const SIZES: Record<Variant, { size: number; weight: 'regular' | 'medium' | 'bold'; line: number }> = {
  display: { size: 30, weight: 'bold', line: 38 }, title: { size: 22, weight: 'bold', line: 30 }, heading: { size: 17, weight: 'bold', line: 24 },
  body: { size: 15, weight: 'regular', line: 22 }, label: { size: 14, weight: 'medium', line: 20 }, caption: { size: 12, weight: 'regular', line: 17 },
};

export function useFont() {
  const { i18n } = useTranslation();
  const lang = (['en', 'gu', 'hi'].includes(i18n.language) ? i18n.language : 'en') as Lang;
  return FONT_FAMILIES[lang];
}

export function T({ variant = 'body', color = colors.text, bold, style, children, ...rest }: {
  variant?: Variant; color?: string; bold?: boolean; style?: StyleProp<TextStyle>; children?: React.ReactNode;
} & React.ComponentProps<typeof Text>) {
  const fonts = useFont();
  const v = SIZES[variant];
  return (
    <Text {...rest} style={[{ fontFamily: fonts[bold ? 'bold' : v.weight], fontSize: v.size, lineHeight: v.line, color }, style]}>
      {children}
    </Text>
  );
}

// ------------------------------------------------------------------ buttons
export function Button({ title, onPress, variant = 'primary', loading, disabled, icon, style, size = 'md' }: {
  title: string; onPress?: () => void; variant?: 'primary' | 'secondary' | 'danger' | 'ghost' | 'success'; loading?: boolean;
  disabled?: boolean; icon?: IconName; style?: StyleProp<ViewStyle>; size?: 'sm' | 'md';
}) {
  const bg = { primary: colors.primary, secondary: colors.primarySoft, danger: colors.danger, ghost: 'transparent', success: colors.success }[variant];
  const fg = { primary: '#fff', secondary: colors.primary, danger: '#fff', ghost: colors.primary, success: '#fff' }[variant];
  const off = disabled || loading;
  return (
    <Pressable
      onPress={off ? undefined : onPress} accessibilityRole="button" accessibilityLabel={title}
      style={({ pressed }) => [styles.btn, size === 'sm' && styles.btnSm, { backgroundColor: bg, opacity: off ? 0.5 : pressed ? 0.85 : 1 }, style]}
    >
      {loading ? <ActivityIndicator color={fg} /> : (
        <>
          {icon && <Ionicons name={icon} size={size === 'sm' ? 16 : 18} color={fg} style={{ marginRight: 6 }} />}
          <T variant="label" color={fg} bold>{title}</T>
        </>
      )}
    </Pressable>
  );
}

export function IconButton({ icon, onPress, color = colors.text, size = 22, label }: { icon: IconName; onPress: () => void; color?: string; size?: number; label: string }) {
  return (
    <Pressable onPress={onPress} hitSlop={10} accessibilityRole="button" accessibilityLabel={label} style={{ padding: 6 }}>
      <Ionicons name={icon} size={size} color={color} />
    </Pressable>
  );
}

// ------------------------------------------------------------------ layout
export function Card({ children, style, onPress, onLongPress, selected }: {
  children: React.ReactNode; style?: StyleProp<ViewStyle>; onPress?: () => void; onLongPress?: () => void; selected?: boolean;
}) {
  const content = [styles.card, selected && { borderColor: colors.primary, borderWidth: 2 }, style];
  if (onPress || onLongPress) {
    return <Pressable onPress={onPress} onLongPress={onLongPress} style={({ pressed }) => [content, pressed && { opacity: 0.9 }]}>{children}</Pressable>;
  }
  return <View style={content}>{children}</View>;
}

export function Screen({ children, scroll = true, refreshing, onRefresh, style, padded = true, edges }: {
  children: React.ReactNode; scroll?: boolean; refreshing?: boolean; onRefresh?: () => void; style?: StyleProp<ViewStyle>; padded?: boolean;
  edges?: ('top' | 'bottom' | 'left' | 'right')[];
}) {
  const pad = padded ? { padding: space.lg } : null;
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={edges ?? ['left', 'right']}>
      {scroll ? (
        <ScrollView
          contentContainerStyle={[pad, { paddingBottom: space.xxl * 2, gap: space.md }, style]} keyboardShouldPersistTaps="handled"
          refreshControl={onRefresh ? <RefreshControl refreshing={!!refreshing} onRefresh={onRefresh} tintColor={colors.primary} /> : undefined}
        >
          {children}
        </ScrollView>
      ) : <View style={[{ flex: 1 }, pad, style]}>{children}</View>}
    </SafeAreaView>
  );
}

export function Row({ children, style, gap = space.sm }: { children: React.ReactNode; style?: StyleProp<ViewStyle>; gap?: number }) {
  return <View style={[{ flexDirection: 'row', alignItems: 'center', gap }, style]}>{children}</View>;
}

export function Divider() {
  return <View style={{ height: StyleSheet.hairlineWidth, backgroundColor: colors.border, marginVertical: space.sm }} />;
}

export function SectionTitle({ children, right }: { children: React.ReactNode; right?: React.ReactNode }) {
  return (
    <Row style={{ justifyContent: 'space-between', marginTop: space.sm }}>
      <T variant="heading">{children}</T>
      {right}
    </Row>
  );
}

// ------------------------------------------------------------------ inputs
export function Input({ label, error, helper, style, ...rest }: TextInputProps & { label?: string; error?: string | null; helper?: string }) {
  const fonts = useFont();
  return (
    <View style={{ gap: 4 }}>
      {label && <T variant="label" color={colors.muted}>{label}</T>}
      <TextInput
        placeholderTextColor={colors.faint}
        {...rest}
        style={[styles.input, { fontFamily: fonts.regular }, error ? { borderColor: colors.danger } : null, rest.multiline && { minHeight: 90, textAlignVertical: 'top' }, style]}
      />
      {error ? <T variant="caption" color={colors.danger}>{error}</T> : helper ? <T variant="caption" color={colors.muted}>{helper}</T> : null}
    </View>
  );
}

export function SegmentedControl<K extends string>({ options, value, onChange }: { options: { key: K; label: string; badge?: number }[]; value: K; onChange: (k: K) => void }) {
  return (
    <View style={styles.segment}>
      {options.map((o) => {
        const active = o.key === value;
        return (
          <Pressable key={o.key} onPress={() => onChange(o.key)} style={[styles.segItem, active && styles.segActive]} accessibilityRole="tab" accessibilityState={{ selected: active }}>
            <T variant="label" color={active ? colors.primary : colors.muted} bold={active}>{o.label}</T>
            {!!o.badge && <Badge text={String(o.badge)} tone="danger" />}
          </Pressable>
        );
      })}
    </View>
  );
}

export function Chip({ label, selected, onPress, icon }: { label: string; selected?: boolean; onPress?: () => void; icon?: IconName }) {
  return (
    <Pressable onPress={onPress} style={[styles.chip, selected && { backgroundColor: colors.primary, borderColor: colors.primary }]}>
      {icon && <Ionicons name={icon} size={14} color={selected ? '#fff' : colors.muted} style={{ marginRight: 4 }} />}
      <T variant="caption" color={selected ? '#fff' : colors.text} bold={selected}>{label}</T>
    </Pressable>
  );
}

type Tone = 'neutral' | 'success' | 'danger' | 'warning' | 'info' | 'primary';
const TONES: Record<Tone, [string, string]> = {
  neutral: ['#F3F4F6', colors.muted], success: [colors.successSoft, colors.success], danger: [colors.dangerSoft, colors.danger],
  warning: [colors.warningSoft, colors.warning], info: [colors.infoSoft, colors.info], primary: [colors.primarySoft, colors.primary],
};
export function Badge({ text, tone = 'neutral', icon }: { text: string; tone?: Tone; icon?: IconName }) {
  const [bg, fg] = TONES[tone];
  return (
    <View style={[styles.badge, { backgroundColor: bg }]}>
      {icon && <Ionicons name={icon} size={11} color={fg} style={{ marginRight: 3 }} />}
      <T variant="caption" color={fg} bold>{text}</T>
    </View>
  );
}

export function Banner({ tone = 'warning', text, icon = 'alert-circle' }: { tone?: Tone; text: string; icon?: IconName }) {
  const [bg, fg] = TONES[tone];
  return (
    <View style={[styles.banner, { backgroundColor: bg }]}>
      <Ionicons name={icon} size={18} color={fg} />
      <T variant="caption" color={fg} style={{ flex: 1 }}>{text}</T>
    </View>
  );
}

// ------------------------------------------------------------------ states
export function LoadingView({ label }: { label?: string }) {
  return (
    <View style={styles.center}>
      <ActivityIndicator color={colors.primary} size="large" />
      {label ? <T variant="caption" color={colors.muted} style={{ marginTop: space.sm }}>{label}</T> : null}
    </View>
  );
}

export function EmptyState({ icon = 'albums-outline', title, subtitle, action }: { icon?: IconName; title: string; subtitle?: string; action?: React.ReactNode }) {
  return (
    <View style={styles.center}>
      <View style={styles.emptyIcon}><Ionicons name={icon} size={30} color={colors.primary} /></View>
      <T variant="heading" style={{ textAlign: 'center' }}>{title}</T>
      {subtitle ? <T color={colors.muted} style={{ textAlign: 'center', marginTop: 4 }}>{subtitle}</T> : null}
      {action ? <View style={{ marginTop: space.lg }}>{action}</View> : null}
    </View>
  );
}

export function errorMessage(e: unknown, t: TFunction): string {
  if (e instanceof ApiError) {
    const key = `errors.${e.code}`;
    const translated = t(key);
    return translated !== key ? translated : e.message;
  }
  return t('common.error');
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const { t } = useTranslation();
  return (
    <View style={styles.center}>
      <View style={[styles.emptyIcon, { backgroundColor: colors.dangerSoft }]}><Ionicons name="cloud-offline-outline" size={30} color={colors.danger} /></View>
      <T style={{ textAlign: 'center' }} color={colors.muted}>{errorMessage(error, t)}</T>
      {onRetry && <Button title={t('common.retry')} onPress={onRetry} variant="secondary" style={{ marginTop: space.lg }} />}
    </View>
  );
}

export function Avatar({ name, size = 40 }: { name?: string | null; size?: number }) {
  const initials = (name ?? '?').split(/\s+/).map((p) => p[0]).slice(0, 2).join('').toUpperCase();
  return (
    <View style={{ width: size, height: size, borderRadius: size / 2, backgroundColor: colors.primarySoft, alignItems: 'center', justifyContent: 'center' }}>
      <T variant="label" color={colors.primary} bold>{initials || '?'}</T>
    </View>
  );
}

// ------------------------------------------------------------------ toast + confirm
type ToastState = { msg: string | null; tone: Tone; show: (msg: string, tone?: Tone) => void; hide: () => void };
export const useToast = create<ToastState>((set) => ({
  msg: null, tone: 'neutral',
  show: (msg, tone = 'neutral') => set({ msg, tone }),
  hide: () => set({ msg: null }),
}));
export const toast = (msg: string, tone: Tone = 'neutral') => useToast.getState().show(msg, tone);

export function ToastHost() {
  const { msg, tone, hide } = useToast();
  const opacity = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    if (!msg) return;
    Animated.timing(opacity, { toValue: 1, duration: 150, useNativeDriver: true }).start();
    const id = setTimeout(() => Animated.timing(opacity, { toValue: 0, duration: 200, useNativeDriver: true }).start(() => hide()), 2600);
    return () => clearTimeout(id);
  }, [msg, hide, opacity]);
  if (!msg) return null;
  const bg = tone === 'danger' ? colors.danger : tone === 'success' ? colors.success : '#111827';
  return (
    <Animated.View pointerEvents="none" style={[styles.toast, { opacity, backgroundColor: bg }]}>
      <T variant="label" color="#fff" style={{ textAlign: 'center' }}>{msg}</T>
    </Animated.View>
  );
}

export function confirm(title: string, message?: string, confirmText = 'OK', destructive = false): Promise<boolean> {
  return new Promise((resolve) => {
    Alert.alert(title, message, [
      { text: 'Cancel', style: 'cancel', onPress: () => resolve(false) },
      { text: confirmText, style: destructive ? 'destructive' : 'default', onPress: () => resolve(true) },
    ], { cancelable: true, onDismiss: () => resolve(false) });
  });
}

const styles = StyleSheet.create({
  btn: { minHeight: 48, borderRadius: radius.md, paddingHorizontal: space.lg, flexDirection: 'row', alignItems: 'center', justifyContent: 'center' },
  btnSm: { minHeight: 36, paddingHorizontal: space.md, borderRadius: radius.sm },
  card: { backgroundColor: colors.card, borderRadius: radius.lg, padding: space.lg, borderWidth: 1, borderColor: colors.border, ...shadow },
  input: { backgroundColor: '#fff', borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, paddingHorizontal: space.md, paddingVertical: 12, fontSize: 16, color: colors.text, minHeight: 48 },
  segment: { flexDirection: 'row', backgroundColor: '#E8EAF2', borderRadius: radius.md, padding: 3 },
  segItem: { flex: 1, paddingVertical: 8, borderRadius: radius.sm + 2, alignItems: 'center', flexDirection: 'row', justifyContent: 'center', gap: 6 },
  segActive: { backgroundColor: '#fff', ...shadow },
  chip: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 12, paddingVertical: 6, borderRadius: radius.pill, borderWidth: 1, borderColor: colors.border, backgroundColor: '#fff' },
  badge: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 8, paddingVertical: 2, borderRadius: radius.pill, alignSelf: 'flex-start' },
  banner: { flexDirection: 'row', alignItems: 'center', gap: 8, padding: space.md, borderRadius: radius.md },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: space.xl, minHeight: 260 },
  emptyIcon: { width: 64, height: 64, borderRadius: 32, backgroundColor: colors.primarySoft, alignItems: 'center', justifyContent: 'center', marginBottom: space.md },
  toast: { position: 'absolute', bottom: 100, left: 24, right: 24, paddingVertical: 12, paddingHorizontal: 16, borderRadius: radius.md, zIndex: 1000 },
});
