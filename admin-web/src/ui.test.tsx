import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { Modal, Pagination } from './components/ui';

describe('Pagination', () => {
  it('disables edges and reports page changes', () => {
    const onChange = vi.fn();
    render(<Pagination total={45} limit={20} offset={0} onChange={onChange} />);
    expect(screen.getByText('1–20 of 45')).toBeInTheDocument();
    expect(screen.getByText('Previous')).toBeDisabled();
    fireEvent.click(screen.getByText('Next'));
    expect(onChange).toHaveBeenCalledWith(20);
  });
  it('disables Next on the last page', () => {
    render(<Pagination total={45} limit={20} offset={40} onChange={() => undefined} />);
    expect(screen.getByText('41–45 of 45')).toBeInTheDocument();
    expect(screen.getByText('Next')).toBeDisabled();
  });
});

describe('Modal', () => {
  it('closes on Escape and backdrop click', () => {
    const onClose = vi.fn();
    render(<Modal title="Suspend" onClose={onClose}><p>body</p></Modal>);
    expect(screen.getByRole('dialog', { name: 'Suspend' })).toBeInTheDocument();
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
